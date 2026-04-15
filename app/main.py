import streamlit as st
import os, shutil, pandas as pd, requests
from datetime import datetime
from sqlalchemy import func

# --- IMPORTS INTERNES ---
from database import SessionLocal, Account, Record, UserProfile
from auth import get_user_info
from parser import check_quota_and_parse
from modules.charts import render_patrimoine_chart, render_account_history, render_allocation_chart
from modules.notifications import send_discord_msg
from fix_db import migrate

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

# --- FONCTION API TAUX DE CHANGE (Mise en cache pour 1h) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_exchange_rates():
    """Récupère les taux de change mondiaux basés sur l'Euro"""
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=3).json()
        return resp.get("rates", {"EUR": 1.0, "CHF": 0.98, "USD": 1.08})
    except:
        return {"EUR": 1.0, "CHF": 0.98, "USD": 1.08} # Fallback de secours

rates = get_exchange_rates()

def convert_to_eur(amount, currency):
    """Convertit n'importe quel montant en Euro"""
    if currency == "EUR" or not currency: return amount
    rate = rates.get(currency.upper(), 1.0)
    return amount / rate if rate > 0 else amount

# --- MIGRATION & SESSION ---
db = SessionLocal()
try: migrate() 
except: pass

try:
    user = get_user_info()
    if not user or not user.get("username"):
        st.warning("Veuillez vous connecter.")
        st.stop()
except: st.stop()

profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"])
    db.add(profile); db.commit(); db.refresh(profile)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🌌 Aura Pro v2.2")
    st.write(f"Utilisateur : **{user['username']}**")
    menu = st.radio("Navigation", ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] if user["is_admin"] else ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"])
    st.divider()
    u_pct = (profile.token_used / profile.token_limit) if (profile.token_limit and profile.token_limit > 0) else 0
    st.write(f"📊 **Quotas Gemini AI**")
    st.progress(min(max(u_pct, 0.0), 1.0), text=f"{profile.token_used:,} / {profile.token_limit:,}")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Dashboard Patrimonial (Consolidé en EUR)")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts:
        st.info("👋 Bienvenue ! Uploadez un relevé dans l'onglet **Mes Comptes**.")
    else:
        total_inv_eur = 0
        total_val_eur = 0
        total_euro_eur = 0
        total_uc_eur = 0
        total_div_eur = 0
        perf_summary = []

        for a in accounts:
            last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
            if last_r:
                # Conversion des données du relevé en EUR pour le Total
                inv_eur = convert_to_eur(last_r.total_invested or 0, a.currency)
                val_eur = convert_to_eur(last_r.total_value or 0, a.currency)
                
                total_inv_eur += inv_eur
                total_val_eur += val_eur
                total_euro_eur += convert_to_eur(last_r.fonds_euro_value or 0, a.currency)
                total_uc_eur += convert_to_eur(last_r.uc_value or 0, a.currency)
                
                divs = sum(r.dividends for r in a.records if r.dividends)
                total_div_eur += convert_to_eur(divs, a.currency)
                
                # Calcul de performance natif (dans la devise du compte)
                investi_natif = last_r.total_invested or 0
                if investi_natif > 0:
                    gain_natif = last_r.total_value - investi_natif
                    pct = (gain_natif / investi_natif) * 100
                else:
                    gain_natif = 0.0
                    pct = 0.0
                
                # Formatage de l'affichage (Devise native + Est. EUR si différent)
                val_str = f"{last_r.total_value:,.2f} {a.currency}"
                if a.currency != "EUR":
                    val_str += f" (~{val_eur:,.0f} €)"
                
                perf_summary.append({
                    "Compte": f"{a.bank_name}",
                    "Type": a.account_type,
                    "Devise": a.currency,
                    "Capital": f"{investi_natif:,.2f} {a.currency}",
                    "Valeur": val_str,
                    "Plus-Value": f"{gain_natif:+.2f} {a.currency}",
                    "Perf.": f"{pct:+.2f}%"
                })

        if perf_summary:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Capital Versé Global", f"{total_inv_eur:,.0f} €")
            k2.metric("Valeur Marché Globale", f"{total_val_eur:,.2f} €")
            gain_net_eur = total_val_eur - total_inv_eur
            p_net = (gain_net_eur / total_inv_eur * 100) if total_inv_eur > 0 else 0
            k3.metric("Plus-Value Nette (Est.)", f"{gain_net_eur:+.2f} €", f"{p_net:+.2f}%")
            k4.metric("Dividendes Globaux", f"{total_div_eur:,.2f} €")

            st.divider()
            c_left, c_right = st.columns(2)
            with c_left: 
                st.subheader("Répartition (en EUR)")
                render_patrimoine_chart(accounts)
            with c_right: 
                st.subheader("Allocation Risque (en EUR)")
                render_allocation_chart(total_euro_eur, total_uc_eur)
            
            st.divider()
            st.subheader("Détail par portefeuille (Devise Native)")
            st.dataframe(pd.DataFrame(perf_summary), hide_index=True, width='stretch')

# --- PAGE : MES COMPTES ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion & Importation")
    up_file = st.file_uploader("Importer un relevé PDF", type="pdf")
    
    if up_file and f"p_{up_file.name}" not in st.session_state:
        with st.status("🔮 Analyse Aura IA...", expanded=True) as s:
            t_path = f"/tmp/{up_file.name}"
            with open(t_path, "wb") as f: f.write(up_file.getvalue())
            res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
            if "error" in res: st.error(res["error"])
            else:
                st.session_state[f"p_{up_file.name}"] = res
                st.session_state[f"t_{up_file.name}"] = t_path
                s.update(label="Analyse terminée !", state="complete")

    if up_file and f"p_{up_file.name}" in st.session_state:
        res = st.session_state[f"p_{up_file.name}"]
        
        # --- MODE ÉDITION MANUELLE AVANT IMPORT ---
        with st.container(border=True):
            st.markdown(f"### 📋 Validation et Correction")
            st.info("💡 L'IA a pré-rempli ces champs. Corrigez-les si nécessaire, notamment si le **Capital Versé** est à 0.")
            
            c_1, c_2, c_3 = st.columns(3)
            edit_bank = c_1.text_input("Banque", value=res.get("bank_name", ""))
            edit_date = c_2.text_input("Date Relevé (YYYY-MM-DD)", value=res.get("date", ""))
            edit_curr = c_3.selectbox("Devise", options=["EUR", "CHF", "USD", "GBP", "CAD"], index=["EUR", "CHF", "USD", "GBP", "CAD"].index(res.get("currency", "EUR")) if res.get("currency", "EUR") in ["EUR", "CHF", "USD", "GBP", "CAD"] else 0)
            
            c_4, c_5, c_6 = st.columns(3)
            edit_val = c_4.number_input("Valeur Totale", value=float(res.get("total_value", 0.0)), step=100.0)
            # LA CORRECTION EST ICI : L'utilisateur peut forcer le capital investi si le document de 2023 ne l'avait pas !
            edit_inv = c_5.number_input("Capital Versé (Investi)", value=float(res.get("total_invested", 0.0)), step=100.0)
            edit_contract = c_6.text_input("N° Contrat", value=res.get("contract_number", ""))
            
            st.divider()
            existing_accs = db.query(Account).filter_by(user_id=user["username"]).all()
            opts = {f"{a.bank_name} (N°{a.contract_number}) - {a.currency}": a.id for a in existing_accs}
            opts["➕ Créer un nouveau compte"] = "NEW"
            target_acc = st.selectbox("Assigner ce relevé à :", options=opts.keys())
            
            if st.button("🚀 Valider définitivement l'importation", type="primary"):
                acc_id = opts[target_acc]
                
                # Vérification de la date
                try: parsed_date = datetime.strptime(edit_date, "%Y-%m-%d").date()
                except: parsed_date = datetime.now().date()

                if acc_id == "NEW":
                    new_a = Account(
                        user_id=user["username"], bank_name=edit_bank,
                        account_type=res.get("account_type", ""), contract_number=edit_contract,
                        currency=edit_curr, total_invested=edit_inv,
                        management_profile=res.get("management_profile")
                    )
                    db.add(new_a); db.commit(); db.refresh(new_a)
                    acc_id = new_a.id
                else:
                    act_acc = db.get(Account, acc_id)
                    act_acc.total_invested = edit_inv

                new_rec = Record(
                    account_id=acc_id, date_releve=parsed_date,
                    total_value=edit_val, total_invested=edit_inv,
                    fonds_euro_value=float(res.get("fonds_euro_value", 0.0)),
                    uc_value=float(res.get("uc_value", 0.0)),
                    dividends=float(res.get("dividends", 0.0)),
                    fees=float(res.get("fees", 0.0))
                )
                db.add(new_rec)
                profile.token_used += res.get("tokens", 0)
                
                store_dir = f"/app/storage/{user['username']}/{acc_id}"
                os.makedirs(store_dir, exist_ok=True)
                if os.path.exists(st.session_state[f"t_{up_file.name}"]):
                    shutil.move(st.session_state[f"t_{up_file.name}"], f"{store_dir}/{edit_date}.pdf")
                
                db.commit()
                if profile.notify_discord:
                    send_discord_msg(profile.discord_webhook, "🌌 Import Réussi", f"Nouveau relevé {edit_bank} ajouté ({edit_val} {edit_curr}).")
                
                del st.session_state[f"p_{up_file.name}"]
                st.success("Données sauvegardées !")
                st.rerun()

    st.divider()
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for acc in accounts:
        with st.expander(f"📂 {acc.bank_name} - {acc.currency} (N°{acc.contract_number})"):
            c_info, c_del = st.columns([0.8, 0.2])
            c_info.write(f"Capital Actuel : **{acc.total_invested:,.2f} {acc.currency}**")
            if c_del.button("🗑️ Supprimer le compte", key=f"del_acc_{acc.id}"):
                db.delete(acc); db.commit(); st.rerun()
            if acc.records:
                render_account_history(acc.records)

# --- PAGE : EXPORT ---
elif menu == "📑 Export":
    st.header("📑 Exportation de données")
    accs = db.query(Account).filter_by(user_id=user["username"]).all()
    if not accs: st.warning("Aucune donnée.")
    else:
        sel = st.multiselect("Comptes", [a.bank_name for a in accs], default=[a.bank_name for a in accs])
        if st.button("Générer CSV"):
            export_data = [{"Banque": a.bank_name, "Date": r.date_releve, "Valeur": r.total_value, "Devise": a.currency} for a in accs if a.bank_name in sel for r in a.records]
            if export_data:
                st.download_button("⬇️ Télécharger", pd.DataFrame(export_data).to_csv(index=False), "export_aura.csv")

# --- PAGE : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    
    with st.container(border=True):
        st.subheader("💱 Devises & Affichage")
        st.info("Sélectionnez les devises que vous utilisez. Aura convertira tout en Euros (€) sur le Dashboard global en utilisant les taux de change en direct.")
        # Conversion du string en liste et inversement
        current_currencies = profile.active_currencies.split(",") if profile.active_currencies else ["EUR"]
        selected_curr = st.multiselect("Devises actives", ["EUR", "CHF", "USD", "GBP", "CAD", "JPY"], default=current_currencies)
        
        st.subheader("🔔 Notifications")
        profile.notify_discord = st.toggle("Activer Discord Webhook", value=profile.notify_discord)
        profile.discord_webhook = st.text_input("URL Webhook", value=profile.discord_webhook, type="password")
        
        if st.button("Enregistrer les préférences"):
            profile.active_currencies = ",".join(selected_curr)
            db.commit(); st.success("Sauvegardé !")

    st.subheader("📁 Explorateur de fichiers")
    root_dir = f"/app/storage/{user['username']}"
    if os.path.exists(root_dir):
        for acc_id in os.listdir(root_dir):
            acc = db.get(Account, int(acc_id))
            st.markdown(f"**{acc.bank_name if acc else acc_id}**")
            for f in os.listdir(os.path.join(root_dir, acc_id)):
                c_f, c_d = st.columns([0.8, 0.2])
                c_f.caption(f"📄 {f}")
                if c_d.button("🗑️", key=f"file_del_{acc_id}_{f}"):
                    os.remove(os.path.join(root_dir, acc_id, f)); st.rerun()

    st.divider()
    if st.button("🚨 RÉINITIALISER TOUT MON COMPTE", type="primary"):
        for a in db.query(Account).filter_by(user_id=user["username"]).all(): db.delete(a)
        if os.path.exists(root_dir): shutil.rmtree(root_dir)
        db.commit(); st.rerun()

# --- PAGE : ADMIN ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration Système")
    t_users, t_files = st.tabs(["👥 Utilisateurs", "🗄️ Stockage"])
    
    with t_users:
        for p in db.query(UserProfile).all():
            with st.container(border=True):
                ca, cb, cc = st.columns([0.2, 0.6, 0.2])
                ca.write(f"👤 **{p.username}**")
                cb.progress(min(p.token_used / p.token_limit if p.token_limit > 0 else 0, 1.0), text=f"{p.token_used:,} / {p.token_limit:,}")
                new_l = cc.number_input("Quota", value=p.token_limit, key=f"lim_{p.id}", step=10000)
                if new_l != p.token_limit: p.token_limit = new_l; db.commit(); st.rerun()

    with t_files:
        if os.path.exists("/app/storage"):
            for u_dir in os.listdir("/app/storage"):
                st.write(f"👤 **User: {u_dir}**")
                for a_dir in os.listdir(os.path.join("/app/storage", u_dir)):
                    st.caption(f"    └─ Compte {a_dir} : {len(os.listdir(os.path.join('/app/storage', u_dir, a_dir)))} fichiers")

db.close()
