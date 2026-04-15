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

st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

@st.cache_data(ttl=3600, show_spinner=False)
def get_exchange_rates():
    try: return requests.get("https://open.er-api.com/v6/latest/EUR", timeout=3).json().get("rates", {"EUR": 1.0, "CHF": 0.98, "USD": 1.08})
    except: return {"EUR": 1.0, "CHF": 0.98, "USD": 1.08}

rates = get_exchange_rates()
def convert_to_eur(amount, currency):
    if currency == "EUR" or not currency: return amount
    rate = rates.get(currency.upper(), 1.0)
    return amount / rate if rate > 0 else amount

db = SessionLocal()
try: migrate() 
except: pass

try:
    user = get_user_info()
    if not user or not user.get("username"): st.warning("Veuillez vous connecter."); st.stop()
except: st.stop()

profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"])
    db.add(profile); db.commit(); db.refresh(profile)

with st.sidebar:
    st.title("🌌 Aura Pro")
    st.write(f"Utilisateur : **{user['username']}**")
    menu = st.radio("Navigation", ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] if user["is_admin"] else ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"])
    st.divider()
    u_pct = (profile.token_used / profile.token_limit) if (profile.token_limit and profile.token_limit > 0) else 0
    st.progress(min(max(u_pct, 0.0), 1.0), text=f"Tokens IA : {profile.token_used:,} / {profile.token_limit:,}")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Dashboard Patrimonial")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts:
        st.info("👋 Bienvenue ! Uploadez un relevé dans l'onglet **Mes Comptes**.")
    else:
        total_inv_eur = 0
        total_val_eur = 0
        total_euro_eur = 0
        total_uc_eur = 0
        perf_summary = []
        all_positions = [] # Pour stocker toutes les actions/ETF

        for a in accounts:
            last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
            if last_r:
                total_inv_eur += convert_to_eur(last_r.total_invested or 0, a.currency)
                total_val_eur += convert_to_eur(last_r.total_value or 0, a.currency)
                total_euro_eur += convert_to_eur(last_r.fonds_euro_value or 0, a.currency)
                total_uc_eur += convert_to_eur(last_r.uc_value or 0, a.currency)
                
                inv_natif = last_r.total_invested or 0
                gain_natif = last_r.total_value - inv_natif
                pct = (gain_natif / inv_natif * 100) if inv_natif > 0 else 0
                
                val_str = f"{last_r.total_value:,.2f} {a.currency}"
                if a.currency != "EUR": val_str += f" (~{convert_to_eur(last_r.total_value, a.currency):,.0f} €)"
                
                perf_summary.append({
                    "Compte": a.bank_name,
                    "Type": a.account_type,
                    "Investi": f"{inv_natif:,.2f} {a.currency}",
                    "Valeur": val_str,
                    "Plus-Value": f"{gain_natif:+.2f} {a.currency}",
                    "Perf.": f"{pct:+.2f}%"
                })

                # Récupération des positions du relevé actuel
                for pos in last_r.positions:
                    all_positions.append({
                        "Compte": a.bank_name,
                        "Actif": pos.name,
                        "Type": pos.asset_type,
                        "Quantité": pos.quantity,
                        "Prix Unitaire": f"{pos.unit_price:,.2f} {a.currency}" if pos.unit_price else "-",
                        "Valeur Totale": f"{pos.total_value:,.2f} {a.currency}"
                    })

        if perf_summary:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Capital Versé Global", f"{total_inv_eur:,.0f} €")
            k2.metric("Valeur Marché Globale", f"{total_val_eur:,.2f} €")
            gain_net_eur = total_val_eur - total_inv_eur
            k3.metric("Plus-Value Nette (Est.)", f"{gain_net_eur:+.2f} €", f"{(gain_net_eur / total_inv_eur * 100):+.2f}%" if total_inv_eur > 0 else "0%")
            k4.metric("Devises Actives", profile.active_currencies)

            st.divider()
            c_left, c_right = st.columns(2)
            with c_left: render_patrimoine_chart(accounts)
            with c_right: render_allocation_chart(total_euro_eur, total_uc_eur)
            
            st.divider()
            st.subheader("📋 Résumé des Portefeuilles")
            st.dataframe(pd.DataFrame(perf_summary), hide_index=True, width='stretch')

            if all_positions:
                st.subheader("🔍 Détail des Actifs (ETF, Actions, Fonds)")
                st.dataframe(pd.DataFrame(all_positions), hide_index=True, width='stretch')

# --- PAGE : MES COMPTES ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion & Importation")
    up_file = st.file_uploader("Importer un relevé PDF", type="pdf")
    
    if up_file and f"p_{up_file.name}" not in st.session_state:
        with st.status("🔮 Extraction ultra-précise (Lignes incluses)...", expanded=True) as s:
            t_path = f"/tmp/{up_file.name}"; open(t_path, "wb").write(up_file.getvalue())
            res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
            if "error" in res: st.error(res["error"])
            else:
                st.session_state[f"p_{up_file.name}"] = res
                st.session_state[f"t_{up_file.name}"] = t_path
                s.update(label="Analyse terminée !", state="complete")

    if up_file and f"p_{up_file.name}" in st.session_state:
        res = st.session_state[f"p_{up_file.name}"]
        with st.container(border=True):
            st.markdown(f"### 📋 Validation ({len(res.get('positions', []))} actifs détectés)")
            
            c_1, c_2, c_3 = st.columns(3)
            edit_bank = c_1.text_input("Banque", value=res.get("bank_name", ""))
            edit_date = c_2.text_input("Date (YYYY-MM-DD)", value=res.get("date", ""))
            curr_list = ["EUR", "CHF", "USD", "GBP", "CAD"]
            edit_curr = c_3.selectbox("Devise", options=curr_list, index=curr_list.index(res.get("currency", "EUR")) if res.get("currency", "EUR") in curr_list else 0)
            
            c_4, c_5, c_6 = st.columns(3)
            edit_val = c_4.number_input("Valeur Totale", value=float(res.get("total_value", 0.0)), step=100.0)
            edit_inv = c_5.number_input("Capital Versé", value=float(res.get("total_invested", 0.0)), step=100.0)
            edit_contract = c_6.text_input("N° Contrat", value=res.get("contract_number", ""))
            
            with st.expander("Voir les actifs extraits"):
                st.json(res.get("positions", []))
            
            existing_accs = db.query(Account).filter_by(user_id=user["username"]).all()
            opts = {f"{a.bank_name} (N°{a.contract_number}) - {a.currency}": a.id for a in existing_accs}
            opts["➕ Créer un nouveau compte"] = "NEW"
            target_acc = st.selectbox("Assigner ce relevé à :", options=opts.keys())
            
            if st.button("🚀 Valider l'importation", type="primary"):
                acc_id = opts[target_acc]
                try: parsed_date = datetime.strptime(edit_date, "%Y-%m-%d").date()
                except: parsed_date = datetime.now().date()

                if acc_id == "NEW":
                    new_a = Account(
                        user_id=user["username"], bank_name=edit_bank, account_type=res.get("account_type", ""), 
                        contract_number=edit_contract, currency=edit_curr, total_invested=edit_inv,
                        management_profile=res.get("management_profile")
                    )
                    db.add(new_a); db.commit(); db.refresh(new_a); acc_id = new_a.id
                else:
                    db.get(Account, acc_id).total_invested = edit_inv

                # Sauvegarde du Record global
                new_rec = Record(
                    account_id=acc_id, date_releve=parsed_date, total_value=edit_val, total_invested=edit_inv,
                    fonds_euro_value=float(res.get("fonds_euro_value", 0.0)), uc_value=float(res.get("uc_value", 0.0)),
                    dividends=float(res.get("dividends", 0.0)), fees=float(res.get("fees", 0.0))
                )
                db.add(new_rec)
                db.commit() # Commit pour avoir l'ID du record
                db.refresh(new_rec)
                
                # Sauvegarde granulaire (Les Positions !)
                for pos in res.get("positions", []):
                    new_pos = Position(
                        record_id=new_rec.id,
                        name=pos.get("name", "Inconnu"),
                        asset_type=pos.get("asset_type", ""),
                        quantity=float(pos.get("quantity", 0.0)),
                        unit_price=float(pos.get("unit_price", 0.0)),
                        total_value=float(pos.get("total_value", 0.0))
                    )
                    db.add(new_pos)

                profile.token_used += res.get("tokens", 0)
                store_dir = f"/app/storage/{user['username']}/{acc_id}"
                os.makedirs(store_dir, exist_ok=True)
                if os.path.exists(st.session_state[f"t_{up_file.name}"]):
                    shutil.move(st.session_state[f"t_{up_file.name}"], f"{store_dir}/{edit_date}.pdf")
                
                db.commit()
                if profile.notify_discord: send_discord_msg(profile.discord_webhook, "🌌 Import", f"Relevé {edit_bank} OK.")
                del st.session_state[f"p_{up_file.name}"]
                st.success("Actifs enregistrés avec succès !"); st.rerun()

    st.divider()
    for acc in db.query(Account).filter_by(user_id=user["username"]).all():
        with st.expander(f"📂 {acc.bank_name} - {acc.currency}"):
            c_info, c_del = st.columns([0.8, 0.2])
            c_info.write(f"Capital Actuel : **{acc.total_invested:,.2f} {acc.currency}**")
            if c_del.button("🗑️ Supprimer", key=f"del_acc_{acc.id}"): db.delete(acc); db.commit(); st.rerun()
            if acc.records: render_account_history(acc.records)

# --- PAGE : EXPORT & PARAMÈTRES & ADMIN (Identique) ---
elif menu == "📑 Export":
    st.header("📑 Exportation")
    accs = db.query(Account).filter_by(user_id=user["username"]).all()
    if accs:
        if st.button("Générer CSV"):
            data = [{"Banque": a.bank_name, "Date": r.date_releve, "Valeur": r.total_value} for a in accs for r in a.records]
            st.download_button("Télécharger", pd.DataFrame(data).to_csv(index=False), "export.csv")

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
        db.commit(); st.rerun()

elif menu == "🛡️ Admin":
    st.header("🛡️ Administration")
    for p in db.query(UserProfile).all():
        with st.container(border=True):
            ca, cb, cc = st.columns([0.2, 0.6, 0.2])
            ca.write(f"👤 **{p.username}**")
            cb.progress(min(p.token_used / p.token_limit if p.token_limit > 0 else 0, 1.0))
            nl = cc.number_input("Quota", value=p.token_limit, key=f"l_{p.id}", step=10000)
            if nl != p.token_limit: p.token_limit = nl; db.commit(); st.rerun()

db.close()
