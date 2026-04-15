import streamlit as st
import os, shutil, pandas as pd, requests
from datetime import datetime
from sqlalchemy import func

# --- IMPORTS INTERNES ---
from database import SessionLocal, Account, Record, Position, UserProfile
from auth import get_user_info
from parser import check_quota_and_parse
from modules.charts import render_patrimoine_chart, render_account_history, render_allocation_chart
from modules.notifications import send_discord_msg
from fix_db import migrate

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

# --- 2. GESTION DES TOKENS (Reset Journalier / Hebdo) ---
def manage_token_resets(profile, db):
    today = datetime.now().date()
    current_week = today.isocalendar()[1]
    updated = False
    if profile.last_daily_reset != today:
        profile.token_used_daily = 0
        profile.last_daily_reset = today
        updated = True
    if profile.last_weekly_reset != current_week:
        profile.token_used_weekly = 0
        profile.last_weekly_reset = current_week
        updated = True
    if updated: db.commit()

# --- 3. API DEVISES ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_exchange_rates():
    try: return requests.get("https://open.er-api.com/v6/latest/EUR", timeout=3).json().get("rates", {"EUR": 1.0, "CHF": 0.98, "USD": 1.08})
    except: return {"EUR": 1.0, "CHF": 0.98, "USD": 1.08}

rates = get_exchange_rates()
def convert_to_eur(amount, currency):
    if currency == "EUR" or not currency: return amount
    rate = rates.get(currency.upper(), 1.0)
    return amount / rate if rate > 0 else amount

# --- 4. INITIALISATION DB & AUTH ---
db = SessionLocal()
try: migrate() 
except: pass

try:
    user = get_user_info()
    if not user or not user.get("username"): st.warning("Veuillez vous connecter."); st.stop()
except: st.stop()

profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"], last_daily_reset=datetime.now().date(), last_weekly_reset=datetime.now().date().isocalendar()[1])
    db.add(profile); db.commit(); db.refresh(profile)

manage_token_resets(profile, db)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🌌 Aura Pro v4.2")
    st.write(f"Utilisateur : **{user['username']}**")
    menu = st.radio("Navigation", ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] if user["is_admin"] else ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"])
    
    st.divider()
    st.subheader("📅 Quota IA Hebdomadaire")
    u_pct = (profile.token_used_weekly / profile.token_limit_weekly) if profile.token_limit_weekly > 0 else 0
    st.progress(min(max(u_pct, 0.0), 1.0), text=f"{profile.token_used_weekly:,} / {profile.token_limit_weekly:,}")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Dashboard Patrimonial")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    if not accounts:
        st.info("👋 Bienvenue ! Ajoutez vos comptes (Livrets ou PDF) dans l'onglet **Mes Comptes**.")
    else:
        total_inv_eur, total_val_eur, total_euro_eur, total_uc_eur, total_div_eur = 0, 0, 0, 0, 0
        perf_summary, all_positions = [], []

        for a in accounts:
            last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
            if last_r:
                total_inv_eur += convert_to_eur(last_r.total_invested or 0, a.currency)
                total_val_eur += convert_to_eur(last_r.total_value or 0, a.currency)
                
                # Si c'est un compte manuel, on considère que c'est du fonds sécurisé (Livre A, LDD...)
                euro_val = (last_r.total_value or 0) if a.is_manual else (last_r.fonds_euro_value or 0)
                total_euro_eur += convert_to_eur(euro_val, a.currency)
                total_uc_eur += convert_to_eur(last_r.uc_value or 0, a.currency)
                
                total_div_eur += convert_to_eur(sum(r.dividends for r in a.records if r.dividends), a.currency)
                
                inv_natif = last_r.total_invested or 0
                gain_natif = last_r.total_value - inv_natif
                pct = (gain_natif / inv_natif * 100) if inv_natif > 0 else 0
                
                type_display = f"{a.account_type} ✍️" if a.is_manual else a.account_type
                val_str = f"{last_r.total_value:,.2f} {a.currency}"
                if a.currency != "EUR": val_str += f" (~{convert_to_eur(last_r.total_value, a.currency):,.0f} €)"
                
                perf_summary.append({
                    "Compte": a.bank_name, "Type": type_display, "Capital": f"{inv_natif:,.2f} {a.currency}",
                    "Valeur": val_str, "Plus-Value": f"{gain_natif:+.2f} {a.currency}", "Perf.": f"{pct:+.2f}%"
                })
                for pos in last_r.positions:
                    all_positions.append({"Compte": a.bank_name, "Actif": pos.name, "Type": pos.asset_type, "Quantité": pos.quantity, "Valeur": f"{pos.total_value:,.2f} {a.currency}"})

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Capital Versé Global", f"{total_inv_eur:,.0f} €")
        k2.metric("Valeur Marché Globale", f"{total_val_eur:,.2f} €")
        gain_tot = total_val_eur - total_inv_eur
        k3.metric("Plus-Value Nette", f"{gain_tot:+.2f} €", f"{(gain_tot/total_inv_eur*100):+.2f}%" if total_inv_eur > 0 else "0%")
        k4.metric("Primes / Intéressement", f"{total_div_eur:,.2f} €")

        st.divider()
        c_l, c_r = st.columns(2)
        with c_l: render_patrimoine_chart(accounts)
        with c_r: render_allocation_chart(total_euro_eur, total_uc_eur)
        
        st.subheader("📋 Résumé des Portefeuilles")
        st.dataframe(pd.DataFrame(perf_summary), hide_index=True, width='stretch') # CORRECTION LOG STREAMLIT
        
        if all_positions:
            st.subheader("🔍 Détail des Actifs (ETF, Fonds, Actions)")
            st.dataframe(pd.DataFrame(all_positions), hide_index=True, width='stretch')

# --- PAGE : MES COMPTES ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion & Importation")
    
    tab_import, tab_manual, tab_manage = st.tabs(["📥 Import PDF (IA)", "✍️ Saisie Manuelle (Livrets)", "📂 Gérer mes comptes"])
    
    # ONGLET 1 : IMPORT IA (Machine Anti-Freeze Absolue)
    with tab_import:
        st.info("Recommandé pour : Assurance Vie, PEA, Epargne Salariale (Amundi, Natixis)...")
        up_file = st.file_uploader("Glissez votre relevé PDF ici", type="pdf")
        
        if up_file:
            file_key = f"file_{up_file.file_id}"
            
            if file_key not in st.session_state:
                st.session_state[file_key] = {"state": "waiting"}
                
            # Étape 1 : Attente d'action
            if st.session_state[file_key]["state"] == "waiting":
                st.success(f"📄 Fichier `{up_file.name}` chargé en mémoire.")
                if st.button("🚀 Lancer l'analyse IA", type="primary"):
                    st.session_state[file_key]["state"] = "processing"
                    st.rerun()
                    
            # Étape 2 : Traitement IA
            elif st.session_state[file_key]["state"] == "processing":
                with st.spinner("🔮 Gemini lit votre document... (Regardez les logs TrueNAS en cas de doute)"):
                    t_path = f"/tmp/{up_file.name}"
                    open(t_path, "wb").write(up_file.getvalue())
                    res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
                    if "error" in res:
                        st.error(res["error"])
                        if st.button("Réessayer"):
                            st.session_state[file_key]["state"] = "waiting"
                            st.rerun()
                    else:
                        st.session_state[file_key]["data"] = res
                        st.session_state[file_key]["state"] = "form"
                        st.rerun()

            # Étape 3 : Formulaire de Validation
            elif st.session_state[file_key]["state"] == "form":
                res = st.session_state[file_key]["data"]
                with st.form(key=f"form_{file_key}"):
                    st.markdown("### 📋 Validation et Corrections")
                    st.info("💡 L'IA a pré-rempli ces champs. Corrigez-les si nécessaire.")
                    
                    c1, c2, c3 = st.columns(3)
                    e_bank = c1.text_input("Banque", value=res.get("bank_name", ""))
                    e_date = c2.text_input("Date (YYYY-MM-DD)", value=res.get("date", ""))
                    c_list = ["EUR", "CHF", "USD", "GBP", "CAD"]
                    e_curr = c3.selectbox("Devise", options=c_list, index=c_list.index(res.get("currency", "EUR")) if res.get("currency", "EUR") in c_list else 0)
                    
                    c4, c5, c6 = st.columns(3)
                    e_val = c4.number_input("Valeur Totale", value=float(res.get("total_value", 0.0)), step=10.0)
                    e_inv = c5.number_input("Capital Versé (ou Versements Nets)", value=float(res.get("total_invested", 0.0)), step=10.0)
                    e_type = c6.text_input("Type de compte", value=res.get("account_type", ""))
                    
                    with st.expander("Voir les actifs extraits par l'IA"):
                        st.json(res.get("positions", []))
                    
                    existing = db.query(Account).filter_by(user_id=user["username"]).all()
                    opts = {f"{a.bank_name} - {a.account_type} (N°{a.contract_number})": a.id for a in existing if not a.is_manual}
                    opts["➕ Créer un nouveau compte"] = "NEW"
                    target = st.selectbox("Assigner à :", options=opts.keys())
                    
                    if st.form_submit_button("🚀 Valider l'import", type="primary"):
                        acc_id = opts[target]
                        try: p_date = datetime.strptime(e_date, "%Y-%m-%d").date()
                        except: p_date = datetime.now().date()

                        if acc_id == "NEW":
                            new_a = Account(user_id=user["username"], bank_name=e_bank, account_type=e_type, contract_number=res.get("contract_number"), currency=e_curr, total_invested=e_inv, is_manual=False)
                            db.add(new_a); db.commit(); db.refresh(new_a); acc_id = new_a.id
                        else:
                            db.get(Account, acc_id).total_invested = e_inv

                        new_r = Record(account_id=acc_id, date_releve=p_date, total_value=e_val, total_invested=e_inv, fonds_euro_value=res.get("fonds_euro_value", 0.0), uc_value=res.get("uc_value", 0.0), dividends=res.get("dividends", 0.0))
                        db.add(new_r); db.commit(); db.refresh(new_r)
                        
                        for pos in res.get("positions", []):
                            db.add(Position(record_id=new_r.id, name=pos['name'], asset_type=pos.get('asset_type'), quantity=pos.get('quantity', 0), unit_price=pos.get('unit_price', 0), total_value=pos['total_value']))
                        
                        tk = res.get("tokens", 0)
                        profile.token_used_weekly += tk
                        profile.token_used_daily += tk
                        profile.token_used_global += tk
                        
                        db.commit()
                        st.session_state[file_key]["state"] = "saved"
                        st.rerun()

            # Étape 4 : Fin
            elif st.session_state[file_key]["state"] == "saved":
                st.success("✅ Document importé avec succès. Fermez-le (croix) pour en importer un autre.")

    # ONGLET 2 : SAISIE MANUELLE (Livrets A, LDD...)
    with tab_manual:
        st.info("Recommandé pour : Livret A, LDDS, LEP, Comptes Courants (Comptes Statiques).")
        with st.form("manual_form", border=True):
            cm1, cm2 = st.columns(2)
            m_bank = cm1.text_input("Nom de la Banque (ex: Caisse d'Epargne, BoursoBank)")
            m_type = cm2.selectbox("Type de Compte", ["Livret A", "LDDS", "LEP", "Compte Courant", "PEL", "Autre"])
            
            cm3, cm4 = st.columns(2)
            m_val = cm3.number_input("Solde Actuel (€)", step=100.0, min_value=0.0)
            m_date = cm4.date_input("Date du solde", value=datetime.now())
            
            if st.form_submit_button("💾 Ajouter / Mettre à jour ce compte", type="primary"):
                if m_bank:
                    exist_m = db.query(Account).filter_by(user_id=user["username"], bank_name=m_bank, account_type=m_type, is_manual=True).first()
                    if not exist_m:
                        exist_m = Account(user_id=user["username"], bank_name=m_bank, account_type=m_type, currency="EUR", total_invested=m_val, is_manual=True)
                        db.add(exist_m); db.commit(); db.refresh(exist_m)
                    else:
                        exist_m.total_invested = m_val 
                    
                    db.add(Record(account_id=exist_m.id, date_releve=m_date, total_value=m_val, total_invested=m_val, fonds_euro_value=m_val))
                    db.commit()
                    st.success(f"{m_type} enregistré !")
                else:
                    st.error("Veuillez renseigner le nom de la banque.")

    # ONGLET 3 : GESTION DES COMPTES
    with tab_manage:
        accounts = db.query(Account).filter_by(user_id=user["username"]).all()
        if not accounts: st.write("Aucun compte.")
        for acc in accounts:
            icon = "✍️" if acc.is_manual else "📂"
            with st.expander(f"{icon} {acc.bank_name} - {acc.account_type} {f'(N°{acc.contract_number})' if acc.contract_number else ''}"):
                c_info, c_del = st.columns([0.8, 0.2])
                c_info.write(f"Solde / Capital : **{acc.total_invested:,.2f} {acc.currency}**")
                if c_del.button("🗑️ Supprimer", key=f"del_acc_{acc.id}"): 
                    db.delete(acc); db.commit(); st.rerun()
                if acc.records: render_account_history(acc.records)

# --- PAGE : EXPORT ---
elif menu == "📑 Export":
    st.header("📑 Exportation CSV")
    accs = db.query(Account).filter_by(user_id=user["username"]).all()
    if accs:
        if st.button("Générer l'export"):
            data = [{"Banque": a.bank_name, "Type": a.account_type, "Manuel": a.is_manual, "Date": r.date_releve, "Valeur": r.total_value} for a in accs for r in a.records]
            st.download_button("Télécharger", pd.DataFrame(data).to_csv(index=False), "export.csv")

# --- PAGE : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    with st.container(border=True):
        st.subheader("💱 Devises")
        curr = profile.active_currencies.split(",") if profile.active_currencies else ["EUR"]
        sel_c = st.multiselect("Devises actives", ["EUR", "CHF", "USD", "GBP", "CAD"], default=curr)
        profile.notify_discord = st.toggle("Discord", profile.notify_discord)
        profile.discord_webhook = st.text_input("Webhook", profile.discord_webhook, type="password")
        if st.button("Enregistrer"): profile.active_currencies = ",".join(sel_c); db.commit(); st.success("OK")

    if st.button("🚨 WIPE DATA", type="primary"):
        for a in db.query(Account).filter_by(user_id=user["username"]).all(): db.delete(a)
        u_path = f"/app/storage/{user['username']}"
        if os.path.exists(u_path): shutil.rmtree(u_path)
        db.commit(); st.rerun()

# --- PAGE : ADMIN ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration des Ressources API")
    tot_jour = db.query(func.sum(UserProfile.token_used_daily)).scalar() or 0
    st.subheader("🌐 Consommation API Gemini (Aujourd'hui)")
    col_api, col_users = st.columns([0.7, 0.3])
    col_api.progress(min(tot_jour / 100000, 1.0), text=f"{tot_jour:,} / 100,000 tokens")
    col_users.metric("Utilisateurs", db.query(UserProfile).count())

    st.divider()
    for p in db.query(UserProfile).all():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([0.2, 0.3, 0.3, 0.2])
            c1.write(f"👤 **{p.username}**")
            c2.write(f"📅 Jour : {p.token_used_daily:,}")
            c3.write(f"🗓️ Hebdo : {p.token_used_weekly:,} / {p.token_limit_weekly:,}")
            nl = c4.number_input("Quota", value=p.token_limit_weekly, key=f"l_{p.id}", step=10000)
            if nl != p.token_limit_weekly: p.token_limit_weekly = nl; db.commit(); st.rerun()

db.close()
