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
    st.metric("Consommation Tokens", f"{profile.token_used:,}", f"/ {profile.token_limit:,}")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Vue Globale du Patrimoine")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts or all(len(a.records) == 0 for a in accounts):
        st.info("👋 Bienvenue ! Commencez par uploader un relevé dans l'onglet 'Mes Comptes'.")
    else:
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
                
                yield_total = ((val_now - val_start) / val_start * 100) if val_start > 0 else 0
                perf_data.append({
                    "Banque": a.bank_name, 
                    "Type": a.account_type, 
                    "Valeur Actuelle": f"{val_now:,.2f} €", 
                    "Rendement": f"{yield_total:+.2f}%"
                })

        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimoine Total", f"{total_eur:,.2f} €")
        m2.metric("Dividendes Perçus", f"{total_div:,.2f} €")
        m3.metric("Comptes Actifs", len(accounts))
        
        st.divider()
        col_chart, col_table = st.columns([0.6, 0.4])
        with col_chart:
            render_patrimoine_chart(accounts)
        with col_table:
            st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)

# --- PAGE : MES COMPTES (Fusion & Upload) ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion des Portefeuilles")
    
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

    if uploaded_file and f"parsed_{uploaded_file.name}" in st.session_state:
        res = st.session_state[f"parsed_{uploaded_file.name}"]
        
        with st.container(border=True):
            st.markdown(f"### 📋 Validation de l'analyse")
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Banque :** {res['bank_name']}")
            c2.write(f"**Montant :** {res['total_value']} {res['currency']}")
            c3.write(f"**Date :** {res['date']}")
            
            existing = db.query(Account).filter_by(user_id=user["username"]).all()
            acc_opts = {f"{a.bank_name} ({a.account_type})": a.id for a in existing}
            acc_opts["➕ Créer un nouveau compte"] = "NEW"
            
            choice = st.selectbox("Assigner ce relevé à :", options=acc_opts.keys())
            
            if st.button("✅ Confirmer l'import et mettre à jour le Dashboard", type="primary"):
                target_id = acc_opts[choice]
                if target_id == "NEW":
                    new_acc = Account(user_id=user["username"], bank_name=res["bank_name"], account_type=res["account_type"], currency=res["currency"])
                    db.add(new_acc); db.commit(); db.refresh(new_acc)
                    target_id = new_acc.id
                
                new_rec = Record(account_id=target_id, date_releve=datetime.strptime(res["date"], "%Y-%m-%d"), 
                                 total_value=res["total_value"], dividends=res.get("dividends", 0), fees=res.get("fees", 0))
                db.add(new_rec)
                
                # Update tokens
                profile.token_used += res.get("tokens", 0)
                
                # Save File
                final_dir = f"/app/storage/{user['username']}/{target_id}"
                os.makedirs(final_dir, exist_ok=True)
                shutil.move(st.session_state[f"temp_path_{uploaded_file.name}"], f"{final_dir}/{res['date']}.pdf")
                
                db.commit()
                if profile.notify_discord:
                    send_discord_msg(profile.discord_webhook, "✅ Nouveau Relevé", f"Import réussi pour {res['bank_name']}. Valeur : {res['total_value']}€")
                
                del st.session_state[f"parsed_{uploaded_file.name}"]
                st.success("Données enregistrées ! Redirection...")
                st.rerun()

    st.divider()
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for a in accounts:
        with st.expander(f"📂 {a.bank_name} - {a.account_type}"):
            if st.button("Supprimer ce compte", key=f"del_{a.id}"):
                db.delete(a); db.commit(); st.rerun()
            if a.records:
                render_account_history(a.records)

# --- PAGE : PARAMÈTRES (Mes fichiers) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Préférences")
    
    # Notifications
    with st.container(border=True):
        profile.notify_discord = st.toggle("Activer notifications Discord", profile.notify_discord)
        profile.discord_webhook = st.text_input("Webhook URL", profile.discord_webhook, type="password")
        if st.button("Enregistrer préférences"): db.commit(); st.success("OK")
    
    # Explorateur de fichiers personnel
    st.subheader("📁 Mes fichiers uploadés")
    user_path = f"/app/storage/{user['username']}"
    if os.path.exists(user_path):
        for acc_dir in os.listdir(user_path):
            acc = db.query(Account).filter_by(id=acc_dir).first()
            acc_name = acc.bank_name if acc else f"Compte #{acc_dir}"
            st.write(f"**{acc_name}**")
            for f in os.listdir(os.path.join(user_path, acc_dir)):
                c1, c2 = st.columns([0.8, 0.2])
                c1.caption(f"📄 {f}")
                if c2.button("🗑️", key=f"del_f_{f}"):
                    os.remove(os.path.join(user_path, acc_dir, f))
                    st.rerun()
    else:
        st.info("Aucun fichier stocké.")

# --- PAGE : ADMIN (Tous les fichiers) ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration Système")
    
    tab_users, tab_files = st.tabs(["👥 Utilisateurs", "🗄️ Tous les fichiers"])
    
    with tab_users:
        for p in db.query(UserProfile).all():
            c1, c2, c3 = st.columns([0.2, 0.6, 0.2])
            c1.write(f"**{p.username}**")
            c2.progress(min(p.token_used/p.token_limit, 1.0), text=f"{p.token_used:,} / {p.token_limit:,} tokens")
            new_lim = c3.number_input("Limite", value=p.token_limit, key=f"p_{p.id}", step=1000)
            if new_lim != p.token_limit: p.token_limit = new_lim; db.commit(); st.rerun()

    with tab_files:
        base_path = "/app/storage"
        if os.path.exists(base_path):
            for u_dir in os.listdir(base_path):
                st.markdown(f"👤 **Utilisateur : {u_dir}**")
                u_path = os.path.join(base_path, u_dir)
                if os.path.isdir(u_path):
                    for a_dir in os.listdir(u_path):
                        for f in os.listdir(os.path.join(u_path, a_dir)):
                            st.caption(f"    └─ 📁 ID Compte {a_dir} : {f}")
        else:
            st.info("Dossier de stockage vide.")

db.close()
