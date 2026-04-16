import streamlit as st
import os, shutil, pandas as pd, requests
from datetime import datetime
from sqlalchemy import func

# --- IMPORTS INTERNES ---
from database import SessionLocal, Account, Record, Position, UserProfile, BankAccount, BankTransaction
from auth import get_user_info
from parser import check_quota_and_parse
from modules.charts import render_patrimoine_chart, render_account_history, render_allocation_chart
from modules.notifications import send_discord_msg
from modules.budget import render_budget_tab # NOUVEAU MODULE IMPORTÉ
from fix_db import migrate

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

def safe_float(value):
    try:
        if value is None or value == "": return 0.0
        if isinstance(value, str):
            value = value.replace('€', '').replace(' ', '').replace(',', '.')
        return float(value)
    except: return 0.0

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

@st.cache_data(ttl=3600, show_spinner=False)
def get_exchange_rates():
    try: return requests.get("https://open.er-api.com/v6/latest/EUR", timeout=3).json().get("rates", {"EUR": 1.0, "CHF": 0.98, "USD": 1.08})
    except: return {"EUR": 1.0, "CHF": 0.98, "USD": 1.08}

rates = get_exchange_rates()
def convert_to_eur(amount, currency):
    if currency == "EUR" or not currency: return amount
    rate = rates.get(currency.upper(), 1.0)
    return amount / rate if rate > 0 else amount

def get_multi_currency_caption(amount_eur, active_currencies):
    currs = [c.strip() for c in active_currencies.split(",") if c.strip() and c.strip() != "EUR"]
    if not currs: return ""
    res = []
    for c in currs:
        rate = rates.get(c, 1.0)
        res.append(f"≈ {amount_eur * rate:,.0f} {c}")
    return " | ".join(res)

# --- INITIALISATION DB ---
try: migrate() 
except: pass
db = SessionLocal()

try:
    user = get_user_info()
    if not user or not user.get("username"): 
        st.warning("Veuillez vous connecter.")
        st.stop()

    profile = db.query(UserProfile).filter_by(username=user["username"]).first()
    if not profile:
        profile = UserProfile(username=user["username"], last_daily_reset=datetime.now().date(), last_weekly_reset=datetime.now().date().isocalendar()[1])
        db.add(profile); db.commit(); db.refresh(profile)

    manage_token_resets(profile, db)

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🌌 Aura Pro v9.0")
        st.write(f"Utilisateur : **{user['username']}**")
        menu = st.radio("Navigation", ["🌍 Dashboard", "💳 Patrimoine & PDF", "💸 Budget & Dépenses", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] if user["is_admin"] else ["🌍 Dashboard", "💳 Patrimoine & PDF", "💸 Budget & Dépenses", "📑 Export", "⚙️ Paramètres"])
        
        st.divider()
        st.subheader("📅 Quota IA Hebdomadaire")
        u_pct = (profile.token_used_weekly / profile.token_limit_weekly) if profile.token_limit_weekly > 0 else 0
        st.progress(min(max(u_pct, 0.0), 1.0), text=f"{profile.token_used_weekly:,} / {profile.token_limit_weekly:,}")

    # --- PAGE : DASHBOARD ---
    if menu == "🌍 Dashboard":
        st.header("📈 Dashboard Patrimonial")
        accounts = db.query(Account).filter_by(user_id=user["username"]).all()
        
        if not accounts:
            st.info("👋 Bienvenue ! Ajoutez vos premiers investissements dans l'onglet **Patrimoine & PDF**.")
        else:
            total_inv_eur, total_val_eur, total_euro_eur, total_uc_eur, total_div_eur = 0, 0, 0, 0, 0
            perf_summary, all_positions = [], []

            for a in accounts:
                last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
                if last_r:
                    total_inv_eur += convert_to_eur(last_r.total_invested or 0, a.currency)
                    total_val_eur += convert_to_eur(last_r.total_value or 0, a.currency)
                    
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
                        all_positions.append({"Compte": a.bank_name, "Actif": pos.name, "Valeur": f"{pos.total_value:,.2f} {a.currency}"})

            k1, k2, k3, k4 = st.columns(4)
            
            k1.metric("Capital Versé Global", f"{total_inv_eur:,.0f} €")
            if sub_inv := get_multi_currency_caption(total_inv_eur, profile.active_currencies): k1.caption(sub_inv)
                
            k2.metric("Valeur Marché Globale", f"{total_val_eur:,.2f} €")
            if sub_val := get_multi_currency_caption(total_val_eur, profile.active_currencies): k2.caption(sub_val)
                
            gain_tot = total_val_eur - total_inv_eur
            k3.metric("Plus-Value Nette", f"{gain_tot:+.2f} €", f"{(gain_tot/total_inv_eur*100):+.2f}%" if total_inv_eur > 0 else "0%")
            if sub_gain := get_multi_currency_caption(gain_tot, profile.active_currencies): k3.caption(sub_gain)
                
            k4.metric("Primes / Intéressement", f"{total_div_eur:,.2f} €")
            if sub_div := get_multi_currency_caption(total_div_eur, profile.active_currencies): k4.caption(sub_div)

            st.divider()
            c_l, c_r = st.columns(2)
            with c_l: render_patrimoine_chart(accounts)
            with c_r: render_allocation_chart(total_euro_eur, total_uc_eur)
            
            st.subheader("📋 Résumé des Portefeuilles")
            st.dataframe(pd.DataFrame(perf_summary), hide_index=True, use_container_width=True)
            if all_positions:
                st.subheader("🔍 Détail des Actifs")
                st.dataframe(pd.DataFrame(all_positions), hide_index=True, use_container_width=True)

    # --- PAGE : PATRIMOINE (PDF) ---
    elif menu == "💳 Patrimoine & PDF":
        st.header("💳 Gestion de vos Investissements")
        tab_import, tab_manual, tab_manage = st.tabs(["📥 Import PDF (IA)", "✍️ Saisie Manuelle", "📂 Gérer mes comptes"])
        
        with tab_import:
            up_file = st.file_uploader("Fichier PDF (Assurance Vie, PEA, Epargne Salariale...)", type="pdf", label_visibility="collapsed")
            if up_file:
                file_key = f"pdf_{up_file.file_id}"
                
                if file_key not in st.session_state and f"done_{file_key}" not in st.session_state:
                    with st.status("🔮 L'IA lit votre document...", expanded=True):
                        t_path = f"/tmp/{up_file.file_id}.pdf"
                        with open(t_path, "wb") as f: f.write(up_file.getvalue())
                        res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
                        
                        if "error" in res: st.error(res["error"])
                        else:
                            st.session_state[file_key] = res
                            st.session_state[f"path_{file_key}"] = t_path
                            db.close(); st.rerun()

                elif isinstance(st.session_state.get(file_key), dict):
                    res = st.session_state[file_key]
                    with st.form(key=f"form_{file_key}", border=True):
                        st.markdown("### 📋 Validation et Corrections")
                        c1, c2, c3 = st.columns(3)
                        e_bank = c1.text_input("Banque", value=res.get("bank_name", ""))
                        e_date = c2.text_input("Date", value=res.get("date", ""))
                        e_curr = c3.selectbox("Devise", ["EUR", "CHF", "USD", "GBP", "CAD"], index=0)
                        
                        c4, c5, c6 = st.columns(3)
                        e_val = c4.number_input("Valeur Totale", value=safe_float(res.get("total_value")))
                        e_inv = c5.number_input("Capital Versé", value=safe_float(res.get("total_invested")))
                        e_div = c6.number_input("Primes/Intéressement", value=safe_float(res.get("dividends")))
                        
                        with st.expander("Voir les actifs détectés"): st.json(res.get("positions", []))
                        
                        existing = db.query(Account).filter_by(user_id=user["username"]).all()
                        opts = {f"{a.bank_name} - {a.account_type} (N°{a.contract_number})": a.id for a in existing if not a.is_manual}
                        opts["➕ Nouveau compte"] = "NEW"
                        target = st.selectbox("Assigner à", options=opts.keys())
                        
                        if st.form_submit_button("💾 Sauvegarder", type="primary"):
                            try:
                                acc_id = opts[target]
                                if acc_id == "NEW":
                                    new_a = Account(user_id=user["username"], bank_name=e_bank, account_type=res.get("account_type",""), currency=e_curr, total_invested=e_inv)
                                    db.add(new_a); db.commit(); db.refresh(new_a); acc_id = new_a.id
                                else:
                                    db.get(Account, acc_id).total_invested = e_inv

                                nr = Record(account_id=acc_id, date_releve=datetime.strptime(e_date, "%Y-%m-%d").date(), total_value=e_val, total_invested=e_inv, fonds_euro_value=safe_float(res.get("fonds_euro_value")), uc_value=safe_float(res.get("uc_value")), dividends=e_div)
                                db.add(nr); db.commit(); db.refresh(nr)
                                
                                for p in res.get("positions", []):
                                    db.add(Position(record_id=nr.id, name=str(p.get('name'))[:255], quantity=safe_float(p.get('quantity')), total_value=safe_float(p.get('total_value'))))
                                
                                profile.token_used_daily += res.get("tokens", 0)
                                profile.token_used_weekly += res.get("tokens", 0)
                                db.commit()
                                st.session_state[f"done_{file_key}"] = True
                                del st.session_state[file_key]
                                db.close(); st.rerun()
                            except Exception as err: st.error(f"Erreur : {err}")
                elif f"done_{file_key}" in st.session_state:
                    st.success("✅ Document importé !")

        with tab_manual:
            with st.form("manual_form", border=True):
                c1, c2 = st.columns(2)
                m_b = c1.text_input("Banque")
                m_t = c2.selectbox("Type", ["Livret A", "LDDS", "Compte Courant", "Autre"])
                c3, c4 = st.columns(2)
                m_v = c3.number_input("Solde (€)")
                m_d = c4.date_input("Date")
                if st.form_submit_button("💾 Ajouter"):
                    if m_b:
                        ex = db.query(Account).filter_by(user_id=user["username"], bank_name=m_b, account_type=m_t, is_manual=True).first()
                        if not ex:
                            ex = Account(user_id=user["username"], bank_name=m_b, account_type=m_t, currency="EUR", total_invested=m_v, is_manual=True)
                            db.add(ex); db.commit(); db.refresh(ex)
                        db.add(Record(account_id=ex.id, date_releve=m_d, total_value=m_v, total_invested=m_v, fonds_euro_value=m_v))
                        db.commit(); st.toast("✅ Ajouté !", icon="💾"); db.close(); st.rerun()

        with tab_manage:
            for acc in db.query(Account).filter_by(user_id=user["username"]).all():
                with st.expander(f"{'✍️' if acc.is_manual else '📂'} {acc.bank_name}"):
                    if st.button("🗑️ Supprimer", key=f"del_{acc.id}"): db.delete(acc); db.commit(); db.close(); st.rerun()
                    if acc.records: render_account_history(acc.records)

    # --- PAGE : BUDGET ---
    elif menu == "💸 Budget & Dépenses":
        render_budget_tab(user["username"], db)

    # --- EXPORT ---
    elif menu == "📑 Export":
        st.header("📑 Exportation de vos données")
        accs = db.query(Account).filter_by(user_id=user["username"]).all()
        bas = db.query(BankAccount).filter_by(user_id=user["username"]).all()
        
        st.subheader("1. Patrimoine")
        if accs and st.button("📥 Exporter le Patrimoine"):
            d = [{"Banque": a.bank_name, "Date": r.date_releve, "Valeur": r.total_value, "Primes": r.dividends} for a in accs for r in a.records]
            st.download_button("Télécharger", pd.DataFrame(d).to_csv(index=False), "patrimoine.csv")
            
        st.subheader("2. Budget")
        if bas and st.button("📥 Exporter le Budget"):
            db_tx = [{"Compte": b.account_name, "Date": t.date, "Libellé": t.label, "Catégorie": t.category, "Montant": t.amount} for b in bas for t in b.transactions]
            st.download_button("Télécharger", pd.DataFrame(db_tx).to_csv(index=False), "budget.csv")

    # --- REGLAGES & ADMIN ---
    elif menu == "⚙️ Paramètres":
        st.header("⚙️ Configuration")
        curr = profile.active_currencies.split(",") if profile.active_currencies else ["EUR"]
        sel = st.multiselect("Devises actives", ["EUR", "CHF", "USD", "GBP"], default=curr)
        if st.button("Enregistrer"): profile.active_currencies = ",".join(sel); db.commit(); st.success("OK")
        
        with st.expander("🚨 Zone de danger"):
            if st.checkbox("Je confirme la suppression") and st.button("🗑️ TOUT EFFACER"):
                for a in db.query(Account).filter_by(user_id=user["username"]).all(): db.delete(a)
                for ba in db.query(BankAccount).filter_by(user_id=user["username"]).all(): db.delete(ba)
                db.commit(); db.close(); st.rerun()

    elif menu == "🛡️ Admin":
        st.header("🛡️ Administration")
        for p in db.query(UserProfile).all():
            st.write(f"👤 {p.username} | Conso : {p.token_used_weekly:,} / {p.token_limit_weekly:,}")

finally:
    db.close()
