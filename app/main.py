import streamlit as st
import os, shutil, pandas as pd
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
st.set_page_config(
    page_title="Aura Wealth Pro", 
    page_icon="🌌", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- MIGRATION AUTOMATIQUE ---
# S'assure que les colonnes (tokens, contract_number, uc_value, etc.) existent
try:
    migrate()
except Exception as e:
    st.sidebar.error(f"Erreur migration : {e}")

# --- STYLE CSS (NÉON & DASHBOARD) ---
st.markdown("""
    <style>
    .stMetric { background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 10px; border-left: 5px solid #a855f7; }
    div[data-testid="stExpander"] { border: 1px solid rgba(168, 85, 247, 0.1); background: rgba(0,0,0,0.1); margin-bottom: 10px; }
    .stButton button { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION ---
user = get_user_info()
db = SessionLocal()

# Récupération/Création du profil utilisateur
profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"])
    db.add(profile)
    db.commit()
    db.refresh(profile)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🌌 Aura Pro v2.0")
    st.write(f"Utilisateur : **{user['username']}**")
    
    menu = st.radio(
        "Navigation", 
        ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] 
        if user["is_admin"] else 
        ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"]
    )
    
    st.divider()
    st.subheader("🤖 Quotas IA")
    u_pct = (profile.token_used / profile.token_limit) if profile.token_limit > 0 else 0
    st.progress(min(u_pct, 1.0), text=f"{profile.token_used:,} / {profile.token_limit:,}")
    if u_pct > 0.9:
        st.warning("Quota bientôt atteint.")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Dashboard Patrimonial")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts or all(len(a.records) == 0 for a in accounts):
        st.info("👋 Bienvenue ! Commencez par uploader un relevé dans l'onglet **Mes Comptes**.")
    else:
        # Calculs des métriques consolidées (basés sur le record le plus récent de chaque compte)
        total_inv = 0
        total_val = 0
        total_euro = 0
        total_uc = 0
        total_div = 0
        
        perf_summary = []
        for a in accounts:
            # On cherche le record le plus récent chronologiquement
            last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
            if last_r:
                total_inv += last_r.total_invested
                total_val += last_r.total_value
                total_euro += last_r.fonds_euro_value
                total_uc += last_r.uc_value
                total_div += sum(r.dividends for r in a.records)
                
                # Performance réelle (Valeur - Investi au même moment)
                gain = last_r.total_value - last_r.total_invested
                pct = (gain / last_r.total_invested * 100) if last_r.total_invested > 0 else 0
                
                perf_summary.append({
                    "Compte": f"{a.bank_name} ({a.account_type})",
                    "N° Contrat": a.contract_number,
                    "Capital": f"{last_r.total_invested:,.2f} €",
                    "Valeur": f"{last_r.total_value:,.2f} €",
                    "Plus-Value": f"{gain:+.2f} €",
                    "Performance": f"{pct:+.2f}%"
                })

        # Affichage KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Capital Versé", f"{total_inv:,.0f} €")
        k2.metric("Valeur Marché", f"{total_val:,.2f} €")
        
        gain_net = total_val - total_inv
        perf_net = (gain_net / total_inv * 100) if total_inv > 0 else 0
        k3.metric("Plus-Value Nette", f"{gain_net:+.2f} €", f"{perf_net:+.2f}%")
        k4.metric("Dividendes", f"{total_div:,.2f} €")

        st.divider()

        # Graphiques
        c_left, c_right = st.columns(2)
        with c_left:
            st.subheader("Répartition par Portefeuille")
            render_patrimoine_chart(accounts)
        with c_right:
            st.subheader("Exposition au Risque")
            render_allocation_chart(total_euro, total_uc)

        st.divider()
        st.subheader("Détail des lignes")
        st.dataframe(pd.DataFrame(perf_summary), hide_index=True, width='stretch')

# --- PAGE : MES COMPTES ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion des Portefeuilles")
    
    # 1. Upload
    up_file = st.file_uploader("Importer un relevé PDF", type="pdf")
    
    if up_file and f"p_{up_file.name}" not in st.session_state:
        with st.status("🔮 Analyse Aura IA (Gemini 2.5 Flash-Lite)...", expanded=True) as s:
            t_path = f"/tmp/{up_file.name}"
            with open(t_path, "wb") as f:
                f.write(up_file.getvalue())
            
            # Appel Parser
            res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
            
            if "error" in res:
                st.error(res["error"])
            else:
                st.session_state[f"p_{up_file.name}"] = res
                st.session_state[f"t_{up_file.name}"] = t_path
                s.update(label="Analyse terminée !", state="complete")

    # 2. Validation de l'import
    if up_file and f"p_{up_file.name}" in st.session_state:
        res = st.session_state[f"p_{up_file.name}"]
        
        with st.container(border=True):
            st.markdown(f"### 🧐 Vérification des données")
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Banque :** {res['bank_name']}")
            col2.write(f"**Date :** {res['date']}")
            col3.write(f"**Contrat :** {res.get('contract_number', 'N/C')}")
            
            ca, cb, cc = st.columns(3)
            ca.metric("Valeur Totale", f"{res['total_value']} €")
            cb.metric("Capital Versé", f"{res['total_invested']} €")
            cc.write(f"**Profil :** {res.get('management_profile', 'N/C')}")
            
            # Fusion avec compte existant
            existing_accs = db.query(Account).filter_by(user_id=user["username"]).all()
            opts = {f"{a.bank_name} - {a.contract_number}": a.id for a in existing_accs}
            opts["➕ Créer un nouveau compte"] = "NEW"
            
            target_acc = st.selectbox("Assigner ce document à :", options=opts.keys())
            
            if st.button("✅ Valider l'importation", type="primary"):
                acc_id = opts[target_acc]
                
                if acc_id == "NEW":
                    new_a = Account(
                        user_id=user["username"], bank_name=res["bank_name"],
                        account_type=res["account_type"], contract_number=res.get("contract_number"),
                        total_invested=res["total_invested"],
                        management_profile=res.get("management_profile"),
                        fiscal_date=datetime.strptime(res["fiscal_date"], "%Y-%m-%d").date() if res.get("fiscal_date") else None
                    )
                    db.add(new_a); db.commit(); db.refresh(new_a)
                    acc_id = new_a.id
                else:
                    # Mise à jour du capital global du compte (Dernier connu)
                    act_acc = db.get(Account, acc_id)
                    act_acc.total_invested = res["total_invested"]

                # Création du Record d'historique
                new_rec = Record(
                    account_id=acc_id,
                    date_releve=datetime.strptime(res["date"], "%Y-%m-%d").date(),
                    total_value=res["total_value"],
                    total_invested=res["total_invested"], # CAPITAL À CETTE DATE PRÉCISE
                    fonds_euro_value=res.get("fonds_euro_value", 0),
                    uc_value=res.get("uc_value", 0),
                    dividends=res.get("dividends", 0),
                    fees=res.get("fees", 0)
                )
                db.add(new_rec)
                profile.token_used += res.get("tokens", 0)
                
                # Rangement physique
                store_dir = f"/app/storage/{user['username']}/{acc_id}"
                os.makedirs(store_dir, exist_ok=True)
                shutil.move(st.session_state[f"t_{up_file.name}"], f"{store_dir}/{res['date']}.pdf")
                
                db.commit()
                
                if profile.notify_discord:
                    send_discord_msg(profile.discord_webhook, "🌌 Import Réussi", f"Nouveau relevé {res['bank_name']} ajouté.")
                
                del st.session_state[f"p_{up_file.name}"]
                st.success("Données fusionnées avec succès !")
                st.rerun()

    st.divider()
    # 3. Liste des comptes
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for acc in accounts:
        with st.expander(f"📂 {acc.bank_name} - {acc.account_type} (N°{acc.contract_number})"):
            c_info, c_del = st.columns([0.8, 0.2])
            c_info.write(f"Profil : {acc.management_profile} | Capital Actuel : {acc.total_invested:,.2f} €")
            if c_del.button("🗑️ Supprimer le compte", key=f"del_acc_{acc.id}"):
                db.delete(acc); db.commit(); st.rerun()
            
            if acc.records:
                render_account_history(acc.records)

# --- PAGE : EXPORT ---
elif menu == "📑 Export":
    st.header("📑 Exportation de données")
    accs = db.query(Account).filter_by(user_id=user["username"]).all()
    if not accs:
        st.warning("Aucune donnée.")
    else:
        sel = st.multiselect("Comptes", [a.bank_name for a in accs], default=[a.bank_name for a in accs])
        if st.button("Générer CSV"):
            export_data = []
            for a in accs:
                if a.bank_name in sel:
                    for r in a.records:
                        export_data.append({"Banque": a.bank_name, "Date": r.date_releve, "Valeur": r.total_value, "Capital": r.total_invested})
            
            if export_data:
                st.download_button("⬇️ Télécharger", pd.DataFrame(export_data).to_csv(index=False), "export_aura.csv")

# --- PAGE : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    
    # Discord
    with st.container(border=True):
        st.subheader("🔔 Notifications")
        profile.notify_discord = st.toggle("Activer Discord Webhook", value=profile.notify_discord)
        profile.discord_webhook = st.text_input("URL Webhook", value=profile.discord_webhook, type="password")
        if st.button("Enregistrer préférences"):
            db.commit(); st.success("OK")

    # Explorateur de fichiers
    st.subheader("📁 Explorateur de fichiers")
    root_dir = f"/app/storage/{user['username']}"
    if os.path.exists(root_dir):
        for acc_id in os.listdir(root_dir):
            acc = db.get(Account, int(acc_id))
            st.markdown(f"**{acc.bank_name if acc else acc_id}**")
            for f in os.listdir(os.path.join(root_dir, acc_id)):
                c_f, c_d = st.columns([0.8, 0.2])
                c_f.caption(f"📄 {f}")
                # ID Unique pour éviter le duplicate key error
                if c_d.button("🗑️", key=f"file_del_{acc_id}_{f}"):
                    os.remove(os.path.join(root_dir, acc_id, f)); st.rerun()
    else:
        st.info("Stockage vide.")

    st.divider()
    if st.button("🚨 RÉINITIALISER TOUT MON COMPTE", type="primary"):
        u_accs = db.query(Account).filter_by(user_id=user["username"]).all()
        for a in u_accs: db.delete(a)
        if os.path.exists(root_dir): shutil.rmtree(root_dir)
        db.commit(); st.rerun()

# --- PAGE : ADMIN ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration Système")
    
    t_users, t_files = st.tabs(["👥 Utilisateurs", "🗄️ Stockage Global"])
    
    with t_users:
        all_p = db.query(UserProfile).all()
        for p in all_p:
            with st.container(border=True):
                ca, cb, cc = st.columns([0.2, 0.6, 0.2])
                ca.write(f"👤 **{p.username}**")
                pct = (p.token_used / p.token_limit) if p.token_limit > 0 else 0
                cb.progress(min(pct, 1.0), text=f"{p.token_used:,} / {p.token_limit:,}")
                new_l = cc.number_input("Quota", value=p.token_limit, key=f"lim_{p.id}", step=10000)
                if new_l != p.token_limit:
                    p.token_limit = new_l; db.commit(); st.rerun()

    with t_files:
        base_s = "/app/storage"
        if os.path.exists(base_s):
            for u_dir in os.listdir(base_s):
                st.write(f"📁 **User: {u_dir}**")
                u_p = os.path.join(base_s, u_dir)
                if os.path.isdir(u_p):
                    for a_dir in os.listdir(u_p):
                        files = os.listdir(os.path.join(u_p, a_dir))
                        st.caption(f"    └─ Compte {a_dir} : {len(files)} fichiers")
        else:
            st.info("Vide.")

db.close()
