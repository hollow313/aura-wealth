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

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(
    page_title="Aura Wealth Pro", 
    page_icon="🌌", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLE CSS PERSONNALISÉ (NÉON) ---
st.markdown("""
    <style>
    .stMetric { background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 10px; border-left: 5px solid #a855f7; }
    div[data-testid="stExpander"] { border: 1px solid rgba(168, 85, 247, 0.2); background: rgba(0,0,0,0.2); }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION AUTH & BASE DE DONNÉES ---
user = get_user_info()
db = SessionLocal()

# On s'assure que le profil utilisateur existe en base
profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"])
    db.add(profile)
    db.commit()
    db.refresh(profile)

# --- NAVIGATION SIDEBAR ---
with st.sidebar:
    st.title("🌌 Aura Pro")
    st.caption(f"Connecté en tant que : **{user['username']}**")
    
    menu = st.radio(
        "Navigation", 
        ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] 
        if user["is_admin"] else 
        ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"]
    )
    
    st.divider()
    # Affichage du quota de tokens
    usage_pct = (profile.token_used / profile.token_limit)
    st.write(f"📊 **Quotas Gemini AI**")
    st.progress(min(usage_pct, 1.0), text=f"{profile.token_used:,} / {profile.token_limit:,}")
    
    if usage_pct > 0.9:
        st.warning("⚠️ Quota presque épuisé !")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Analyse Patrimoniale Avancée")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts or all(len(a.records) == 0 for a in accounts):
        st.info("👋 Bienvenue ! Veuillez importer vos premiers relevés dans l'onglet 'Mes Comptes'.")
    else:
        # 1. Calculs des métriques consolidées
        total_invested = sum(a.total_invested for a in accounts)
        total_current = 0
        total_euro = 0
        total_uc = 0
        total_div = 0
        
        perf_data = []
        for a in accounts:
            if a.records:
                last_r = sorted(a.records, key=lambda r: r.date_releve)[-1]
                total_current += last_r.total_value
                total_euro += last_r.fonds_euro_value
                total_uc += last_r.uc_value
                total_div += sum(r.dividends for r in a.records)
                
                # Performance réelle (Valeur - Investi)
                gain = last_r.total_value - a.total_invested
                gain_pct = (gain / a.total_invested * 100) if a.total_invested > 0 else 0
                
                perf_data.append({
                    "Banque": a.bank_name,
                    "Type": a.account_type,
                    "Capital": f"{a.total_invested:,.0f} €",
                    "Valeur": f"{last_r.total_value:,.2f} €",
                    "Gain": f"{gain:+.2f} €",
                    "Rendement": f"{gain_pct:+.2f}%"
                })

        # 2. Barre de KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Capital Versé", f"{total_invested:,.0f} €")
        c2.metric("Valeur Marché", f"{total_current:,.2f} €")
        
        net_gain = total_current - total_invested
        net_pct = (net_gain / total_invested * 100) if total_invested > 0 else 0
        c3.metric("Plus-Value Nette", f"{net_gain:+.2f} €", f"{net_pct:+.2f}%")
        c4.metric("Dividendes", f"{total_div:,.2f} €")

        st.divider()

        # 3. Graphiques
        col_pie, col_alloc = st.columns(2)
        with col_pie:
            st.subheader("Répartition par Contrat")
            render_patrimoine_chart(accounts)
        with col_alloc:
            st.subheader("Allocation Sécurité vs Risque")
            render_allocation_chart(total_euro, total_uc)

        st.divider()
        st.subheader("Détail des Performances")
        st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)

# --- PAGE : MES COMPTES ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion des Portefeuilles")
    
    # 1. ZONE D'UPLOAD
    uploaded_file = st.file_uploader("Importer un relevé (PDF)", type="pdf")
    
    if uploaded_file and f"parsed_{uploaded_file.name}" not in st.session_state:
        with st.status("🔮 Aura IA analyse votre document...", expanded=True) as status:
            temp_path = f"/tmp/{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Analyse via Gemini 2.5 Flash-Lite
            res = check_quota_and_parse(temp_path, os.getenv("GEMINI_API_KEY"))
            
            if "error" in res:
                st.error(res["error"])
            else:
                st.session_state[f"parsed_{uploaded_file.name}"] = res
                st.session_state[f"temp_path_{uploaded_file.name}"] = temp_path
                status.update(label="✅ Analyse réussie !", state="complete")

    # 2. VALIDATION ET FUSION
    if uploaded_file and f"parsed_{uploaded_file.name}" in st.session_state:
        res = st.session_state[f"parsed_{uploaded_file.name}"]
        
        with st.container(border=True):
            st.markdown("### 📋 Confirmation des données")
            col_a, col_b, col_c = st.columns(3)
            col_a.write(f"**Banque :** {res['bank_name']}")
            col_b.write(f"**Date :** {res['date']}")
            col_c.write(f"**Contrat :** {res.get('contract_number', 'N/C')}")
            
            col_d, col_e, col_f = st.columns(3)
            col_d.metric("Valeur Totale", f"{res['total_value']} €")
            col_e.metric("Capital Versé", f"{res['total_invested']} €")
            col_f.write(f"**Profil :** {res.get('management_profile', 'N/C')}")
            
            # Système de Fusion
            existing = db.query(Account).filter_by(user_id=user["username"]).all()
            options = {f"{a.bank_name} - {a.account_type} (N°{a.contract_number})": a.id for a in existing}
            options["➕ Créer un nouveau portefeuille"] = "NEW"
            
            target = st.selectbox("Assigner ce relevé à quel compte ?", options=options.keys())
            
            if st.button("🚀 Valider l'importation", type="primary", use_container_width=True):
                target_id = options[target]
                
                if target_id == "NEW":
                    acc = Account(
                        user_id=user["username"], bank_name=res["bank_name"],
                        account_type=res["account_type"], contract_number=res.get("contract_number"),
                        total_invested=res["total_invested"], 
                        management_profile=res.get("management_profile"),
                        fiscal_date=datetime.strptime(res["fiscal_date"], "%Y-%m-%d").date() if res.get("fiscal_date") else None
                    )
                    db.add(acc); db.commit(); db.refresh(acc)
                    target_id = acc.id
                else:
                    # On met à jour le capital investi sur le compte existant
                    acc = db.query(Account).get(target_id)
                    acc.total_invested = res["total_invested"]

                # Création du Record
                new_rec = Record(
                    account_id=target_id,
                    date_releve=datetime.strptime(res["date"], "%Y-%m-%d").date(),
                    total_value=res["total_value"],
                    fonds_euro_value=res.get("fonds_euro_value", 0),
                    uc_value=res.get("uc_value", 0),
                    dividends=res.get("dividends", 0),
                    fees=res.get("fees", 0)
                )
                db.add(new_rec)
                
                # Mise à jour des tokens
                profile.token_used += res.get("tokens", 0)
                
                # Rangement physique du PDF
                storage_path = f"/app/storage/{user['username']}/{target_id}"
                os.makedirs(storage_path, exist_ok=True)
                shutil.move(st.session_state[f"temp_path_{uploaded_file.name}"], f"{storage_path}/{res['date']}.pdf")
                
                db.commit()
                
                # Notification Discord
                if profile.notify_discord:
                    send_discord_msg(profile.discord_webhook, "🌌 Nouveau Relevé", 
                        f"L'utilisateur {user['username']} a importé {res['bank_name']}.\nValeur : {res['total_value']} €")
                
                del st.session_state[f"parsed_{uploaded_file.name}"]
                st.success("Données fusionnées ! Mise à jour du Dashboard...")
                st.rerun()

    st.divider()
    # 3. LISTE DES COMPTES
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for acc in accounts:
        with st.expander(f"📂 {acc.bank_name} - {acc.account_type} (Contrat {acc.contract_number})"):
            c1, c2 = st.columns([0.8, 0.2])
            c1.info(f"Profil : {acc.management_profile} | Capital Versé : {acc.total_invested:,.2f} €")
            if c2.button("🗑️ Supprimer", key=f"del_{acc.id}"):
                db.delete(acc); db.commit(); st.rerun()
            
            if acc.records:
                render_account_history(acc.records)

# --- PAGE : EXPORT ---
elif menu == "📑 Export":
    st.header("📑 Exportation des données")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts:
        st.warning("Aucune donnée à exporter.")
    else:
        selected = st.multiselect("Choisir les comptes", [f"{a.bank_name} ({a.account_type})" for a in accounts])
        c1, c2 = st.columns(2)
        start_d = c1.date_input("Du", datetime(2024, 1, 1))
        end_d = c2.date_input("Au", datetime.now())
        
        if st.button("Générer le rapport CSV"):
            export_list = []
            for a in accounts:
                if f"{a.bank_name} ({a.account_type})" in selected:
                    for r in a.records:
                        if start_d <= r.date_releve <= end_d:
                            export_list.append({
                                "Banque": a.bank_name, "Date": r.date_releve, 
                                "Valeur": r.total_value, "Dividendes": r.dividends
                            })
            
            if export_list:
                df_export = pd.DataFrame(export_list)
                st.download_button("⬇️ Télécharger CSV", df_export.to_csv(index=False), "aura_wealth_export.csv")
            else:
                st.error("Aucune donnée sur cette période.")

# --- PAGE : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Préférences & Fichiers")
    
    # Notifications Discord
    with st.container(border=True):
        st.subheader("🔔 Notifications")
        profile.notify_discord = st.toggle("Activer Discord Webhook", value=profile.notify_discord)
        profile.discord_webhook = st.text_input("URL Webhook", value=profile.discord_webhook, type="password")
        if st.button("Enregistrer les paramètres"):
            db.commit(); st.success("Préférences enregistrées.")

    # Explorateur de fichiers personnel
    st.subheader("📁 Mes documents PDF")
    user_root = f"/app/storage/{user['username']}"
    if os.path.exists(user_root):
        for acc_id in os.listdir(user_root):
            acc = db.query(Account).get(acc_id)
            name = acc.bank_name if acc else f"ID {acc_id}"
            st.write(f"**{name}**")
            for f in os.listdir(os.path.join(user_root, acc_id)):
                col_f, col_d = st.columns([0.8, 0.2])
                col_f.caption(f"📄 {f}")
                if col_d.button("🗑️", key=f"file_{f}"):
                    os.remove(os.path.join(user_root, acc_id, f))
                    st.rerun()
    else:
        st.info("Aucun fichier stocké.")

    st.divider()
    if st.button("🚨 WIPE : Supprimer TOUTES mes données", type="primary"):
        accs = db.query(Account).filter_by(user_id=user["username"]).all()
        for a in accs: db.delete(a)
        if os.path.exists(user_root): shutil.rmtree(user_root)
        db.commit(); st.rerun()

# --- PAGE : ADMIN ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration Système")
    
    t1, t2 = st.tabs(["👥 Utilisateurs", "🗄️ Stockage Global"])
    
    with t1:
        profiles = db.query(UserProfile).all()
        for p in profiles:
            with st.container(border=True):
                ca, cb, cc = st.columns([0.2, 0.6, 0.2])
                ca.write(f"**{p.username}**")
                usage = (p.token_used / p.token_limit)
                cb.progress(min(usage, 1.0), text=f"{p.token_used:,} tokens utilisés")
                new_lim = cc.number_input("Limite", value=p.token_limit, key=f"lim_{p.id}", step=10000)
                if new_lim != p.token_limit:
                    p.token_limit = new_lim; db.commit(); st.rerun()

    with t2:
        base = "/app/storage"
        if os.path.exists(base):
            for u_dir in os.listdir(base):
                st.markdown(f"👤 **{u_dir}**")
                u_path = os.path.join(base, u_dir)
                if os.path.isdir(u_path):
                    for a_dir in os.listdir(u_path):
                        files = os.listdir(os.path.join(u_path, a_dir))
                        st.caption(f"    └─ 📁 Compte {a_dir} : {len(files)} documents")
        else:
            st.info("Stockage vide.")

db.close()
