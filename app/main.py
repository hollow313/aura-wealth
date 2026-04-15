import streamlit as st
import os, shutil, pandas as pd
from datetime import datetime
from sqlalchemy import func
from database import SessionLocal, Account, Record, UserProfile
from auth import get_user_info
from parser import check_quota_and_parse
from modules.charts import render_patrimoine_chart, render_account_history
from modules.notifications import send_discord_msg

st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide")

# --- AUTH & DB ---
user = get_user_info()
db = SessionLocal()
profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"])
    db.add(profile); db.commit(); db.refresh(profile)

# --- NAVIGATION ---
with st.sidebar:
    st.title("🌌 Aura Pro")
    menu = st.radio("Navigation", ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] if user["is_admin"] else ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"])
    st.divider()
    st.info(f"Tokens: {profile.token_used:,} / {profile.token_limit:,}")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Vue Globale du Patrimoine")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts:
        st.info("Commencez par uploader un relevé dans 'Mes Comptes'.")
    else:
        # Calculs KPIs
        total_eur = 0
        total_div = 0
        perf_data = []
        
        for a in accounts:
            if a.records:
                sorted_recs = sorted(a.records, key=lambda r: r.date_releve)
                val_now = sorted_recs[-1].total_value
                val_start = sorted_recs[0].total_value
                total_eur += val_now
                total_div += sum(r.dividends for r in a.records)
                
                # Calcul Rendement
                yield_total = ((val_now - val_start) / val_start * 100) if val_start > 0 else 0
                perf_data.append({"Compte": a.bank_name, "Actuel": val_now, "Rendement": f"{yield_total:+.2f}%"})

        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimoine Total", f"{total_eur:,.2f} €")
        m2.metric("Dividendes Perçus", f"{total_div:,.2f} €")
        m3.metric("Nombre de Comptes", len(accounts))
        
        render_patrimoine_chart(accounts)
        st.table(pd.DataFrame(perf_data))

# --- PAGE : MES COMPTES (Fusion & Upload) ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion des Portefeuilles")
    
    # Logic Upload
    uploaded_file = st.file_uploader("Glisser un relevé PDF", type="pdf")
    if uploaded_file and f"parsed_{uploaded_file.name}" not in st.session_state:
        with st.status("🔮 Extraction Gemini 2.5 Flash-Lite...") as s:
            path = f"/tmp/{uploaded_file.name}"
            with open(path, "wb") as f: f.write(uploaded_file.getvalue())
            
            res = check_quota_and_parse(path, os.getenv("GEMINI_API_KEY"))
            if "error" in res: st.error(res["error"])
            else:
                st.session_state[f"parsed_{uploaded_file.name}"] = res
                st.session_state[f"temp_path_{uploaded_file.name}"] = path
                s.update(label="Analyse terminée !", state="complete")

    # Si analysé, demander confirmation
    if uploaded_file and f"parsed_{uploaded_file.name}" in st.session_state:
        res = st.session_state[f"parsed_{uploaded_file.name}"]
        st.success(f"Détecté : {res['bank_name']} - {res['total_value']} {res['currency']}")
        
        existing = db.query(Account).filter_by(user_id=user["username"]).all()
        acc_opts = {f"{a.bank_name} ({a.account_type})": a.id for a in existing}
        acc_opts["➕ Créer un nouveau compte"] = "NEW"
        
        choice = st.selectbox("Assigner à quel compte ?", options=acc_opts.keys())
        
        if st.button("Confirmer l'import"):
            target_id = acc_opts[choice]
            if target_id == "NEW":
                new_acc = Account(user_id=user["username"], bank_name=res["bank_name"], account_type=res["account_type"], currency=res["currency"])
                db.add(new_acc); db.commit(); db.refresh(new_acc)
                target_id = new_acc.id
            
            new_rec = Record(account_id=target_id, date_releve=datetime.strptime(res["date"], "%Y-%m-%d"), 
                             total_value=res["total_value"], dividends=res["dividends"], fees=res["fees"])
            db.add(new_rec)
            profile.token_used += res["tokens"]
            
            # Déplacement physique
            final_dir = f"/app/storage/{user['username']}/{target_id}"
            os.makedirs(final_dir, exist_ok=True)
            shutil.move(st.session_state[f"temp_path_{uploaded_file.name}"], f"{final_dir}/{res['date']}.pdf")
            
            db.commit()
            if profile.notify_discord:
                send_discord_msg(profile.discord_webhook, "✅ Nouveau Relevé", f"Import réussi pour {res['bank_name']}. Valeur : {res['total_value']}€")
            
            del st.session_state[f"parsed_{uploaded_file.name}"]
            st.rerun()

    # Liste des comptes
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for a in accounts:
        with st.expander(f"📂 {a.bank_name} - {a.account_type}"):
            if st.button("Supprimer le compte", key=f"del_{a.id}"):
                db.delete(a); db.commit(); st.rerun()
            render_account_history(a.records)

# --- PAGE : EXPORT ---
elif menu == "📑 Export":
    st.header("📑 Export Expert")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    sel = st.multiselect("Comptes", [a.bank_name for a in accounts])
    d1 = st.date_input("Début", datetime(2025,1,1))
    d2 = st.date_input("Fin", datetime.now())
    
    if st.button("Générer CSV"):
        out = []
        for a in accounts:
            if a.bank_name in sel:
                for r in a.records:
                    if d1 <= r.date_releve <= d2:
                        out.append({"Banque": a.bank_name, "Date": r.date_releve, "Valeur": r.total_value, "Dividendes": r.dividends})
        st.download_button("Télécharger", pd.DataFrame(out).to_csv(), "aura_export.csv")

# --- PAGE : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Préférences")
    profile.notify_discord = st.toggle("Activer Discord", profile.notify_discord)
    profile.discord_webhook = st.text_input("Webhook URL", profile.discord_webhook, type="password")
    if st.button("Sauvegarder"): db.commit(); st.success("OK")
    
    st.divider()
    if st.button("🚨 Réinitialiser toutes mes données", type="primary"):
        accs = db.query(Account).filter_by(user_id=user["username"]).all()
        for a in accs: db.delete(a)
        if os.path.exists(f"/app/storage/{user['username']}"): shutil.rmtree(f"/app/storage/{user['username']}")
        db.commit(); st.rerun()

# --- PAGE : ADMIN ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration")
    for p in db.query(UserProfile).all():
        c1, c2, c3 = st.columns([0.2, 0.6, 0.2])
        c1.write(p.username)
        c2.progress(min(p.token_used/p.token_limit, 1.0), text=f"{p.token_used} / {p.token_limit}")
        new_lim = c3.number_input("Limite", value=p.token_limit, key=f"p_{p.id}")
        if new_lim != p.token_limit: p.token_limit = new_lim; db.commit(); st.rerun()

db.close()
