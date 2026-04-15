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

# --- 1. CONFIGURATION (Impérativement en premier) ---
st.set_page_config(
    page_title="Aura Wealth Pro", 
    page_icon="🌌", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. INITIALISATION SESSION STATE ---
if "confirm_wipe" not in st.session_state:
    st.session_state.confirm_wipe = False

# --- 3. MIGRATION & CONNEXION DB ---
db = SessionLocal()
try:
    migrate() # Vérifie et crée les colonnes manquantes (contract_number, uc_value, etc.)
except Exception as e:
    st.sidebar.error(f"⚠️ Erreur Migration : {e}")

# --- 4. STYLE CSS NÉON ---
st.markdown("""
    <style>
    .stMetric { background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 10px; border-left: 5px solid #a855f7; }
    div[data-testid="stExpander"] { border: 1px solid rgba(168, 85, 247, 0.1); background: rgba(0,0,0,0.1); margin-bottom: 10px; }
    .stButton button { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 5. AUTHENTIFICATION ---
try:
    user = get_user_info()
    if not user or not user.get("username"):
        st.warning("Veuillez vous connecter pour accéder à Aura.")
        st.stop()
except Exception as e:
    st.error(f"Erreur d'authentification : {e}")
    st.stop()

# --- 6. CHARGEMENT PROFIL ---
profile = db.query(UserProfile).filter_by(username=user["username"]).first()
if not profile:
    profile = UserProfile(username=user["username"])
    db.add(profile)
    db.commit()
    db.refresh(profile)

# --- 7. NAVIGATION SIDEBAR ---
with st.sidebar:
    st.title("🌌 Aura Pro v2.1")
    st.write(f"Utilisateur : **{user['username']}**")
    
    menu = st.radio(
        "Navigation", 
        ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] 
        if user["is_admin"] else 
        ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"]
    )
    
    st.divider()
    st.subheader("🤖 Quotas Gemini AI")
    u_pct = (profile.token_used / profile.token_limit) if (profile.token_limit and profile.token_limit > 0) else 0
    st.progress(min(max(u_pct, 0.0), 1.0), text=f"{profile.token_used:,} / {profile.token_limit:,}")

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Dashboard Patrimonial")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts:
        st.info("👋 Bienvenue ! Commencez par uploader un relevé dans l'onglet **Mes Comptes**.")
    else:
        total_inv = 0
        total_val = 0
        total_euro = 0
        total_uc = 0
        total_div = 0
        perf_summary = []

        for a in accounts:
            # Récupération du relevé le plus récent (celui qui fait foi pour la valeur actuelle)
            last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
            if last_r:
                total_inv += (last_r.total_invested or 0)
                total_val += (last_r.total_value or 0)
                total_euro += (last_r.fonds_euro_value or 0)
                total_uc += (last_r.uc_value or 0)
                total_div += sum(r.dividends for r in a.records if r.dividends)
                
                # Performance réelle basée sur le capital de CE relevé
                investi = last_r.total_invested or 1
                gain = last_r.total_value - investi
                pct = (gain / investi * 100)
                
                perf_summary.append({
                    "Compte": f"{a.bank_name}",
                    "Type": a.account_type,
                    "Capital": f"{investi:,.2f} €",
                    "Valeur": f"{last_r.total_value:,.2f} €",
                    "Plus-Value": f"{gain:+.2f} €",
                    "Perf.": f"{pct:+.2f}%"
                })

        if perf_summary:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Capital Versé", f"{total_inv:,.0f} €")
            k2.metric("Valeur Marché", f"{total_val:,.2f} €")
            gain_net = total_val - total_inv
            p_net = (gain_net / total_inv * 100) if total_inv > 0 else 0
            k3.metric("Plus-Value Nette", f"{gain_net:+.2f} €", f"{p_net:+.2f}%")
            k4.metric("Dividendes", f"{total_div:,.2f} €")

            st.divider()
            c_left, c_right = st.columns(2)
            with c_left: 
                st.subheader("Répartition par contrat")
                render_patrimoine_chart(accounts)
            with c_right: 
                st.subheader("Allocation Risque")
                render_allocation_chart(total_euro, total_uc)
            
            st.divider()
            st.subheader("Détail des Portefeuilles")
            st.dataframe(pd.DataFrame(perf_summary), hide_index=True, width='stretch')

# --- PAGE : MES COMPTES ---
elif menu == "💳 Mes Comptes":
    st.header("💳 Gestion des Portefeuilles")
    up_file = st.file_uploader("Importer un relevé PDF", type="pdf")
    
    if up_file and f"p_{up_file.name}" not in st.session_state:
        with st.status("🔮 Analyse Aura IA...", expanded=True) as s:
            t_path = f"/tmp/{up_file.name}"
            with open(t_path, "wb") as f: f.write(up_file.getvalue())
            res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
            if "error" in res:
                st.error(res["error"])
            else:
                st.session_state[f"p_{up_file.name}"] = res
                st.session_state[f"t_{up_file.name}"] = t_path
                s.update(label="Analyse terminée !", state="complete")

    if up_file and f"p_{up_file.name}" in st.session_state:
        res = st.session_state[f"p_{up_file.name}"]
        with st.container(border=True):
            st.markdown(f"### 📋 Validation de l'analyse")
            st.write(f"**{res['bank_name']}** | Date : {res['date']} | Contrat : {res.get('contract_number', 'N/C')}")
            st.write(f"Valeur : **{res['total_value']} €** | Capital : **{res['total_invested']} €**")
            
            existing_accs = db.query(Account).filter_by(user_id=user["username"]).all()
            opts = {f"{a.bank_name} (N°{a.contract_number})": a.id for a in existing_accs}
            opts["➕ Créer un nouveau compte"] = "NEW"
            target_acc = st.selectbox("Assigner ce relevé à :", options=opts.keys())
            
            if st.button("🚀 Confirmer l'importation", type="primary"):
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
                    # On met à jour le dernier capital connu du compte
                    a_obj = db.get(Account, acc_id)
                    a_obj.total_invested = res["total_invested"]

                # Création du Record
                new_rec = Record(
                    account_id=acc_id,
                    date_releve=datetime.strptime(res["date"], "%Y-%m-%d").date(),
                    total_value=res["total_value"],
                    total_invested=res["total_invested"],
                    fonds_euro_value=res.get("fonds_euro_value", 0),
                    uc_value=res.get("uc_value", 0),
                    dividends=res.get("dividends", 0),
                    fees=res.get("fees", 0)
                )
                db.add(new_rec)
                profile.token_used += res.get("tokens", 0)
                
                # Rangement physique du PDF sur TrueNAS
                store_dir = f"/app/storage/{user['username']}/{acc_id}"
                os.makedirs(store_dir, exist_ok=True)
                if os.path.exists(st.session_state[f"t_{up_file.name}"]):
                    shutil.move(st.session_state[f"t_{up_file.name}"], f"{store_dir}/{res['date']}.pdf")
                
                db.commit()
                if profile.notify_discord:
                    send_discord_msg(profile.discord_webhook, "✅ Import Réussi", f"Nouveau relevé {res['bank_name']} ({res['total_value']} €)")
                
                del st.session_state[f"p_{up_file.name}"]
                st.success("Données fusionnées avec succès !")
                st.rerun()

    st.divider()
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for acc in accounts:
        with st.expander(f"📂 {acc.bank_name} - N°{acc.contract_number}"):
            c1, c2 = st.columns([0.8, 0.2])
            c1.write(f"Profil : **{acc.management_profile}** | Capital Actuel : **{acc.total_invested:,.2f} €**")
            if c2.button("🗑️ Supprimer le compte", key=f"del_acc_{acc.id}"):
                db.delete(acc); db.commit(); st.rerun()
            if acc.records:
                render_account_history(acc.records)

# --- PAGE : EXPORT ---
elif menu == "📑 Export":
    st.header("📑 Exportation CSV")
    accs = db.query(Account).filter_by(user_id=user["username"]).all()
    if not accs:
        st.warning("Aucune donnée à exporter.")
    else:
        sel = st.multiselect("Comptes à inclure", [a.bank_name for a in accs], default=[a.bank_name for a in accs])
        if st.button("Générer l'export"):
            data = []
            for a in accs:
                if a.bank_name in sel:
                    for r in a.records:
                        data.append({
                            "Banque": a.bank_name, 
                            "Date": r.date_releve, 
                            "Valeur": r.total_value, 
                            "Capital": r.total_invested
                        })
            if data:
                st.download_button("⬇️ Télécharger CSV", pd.DataFrame(data).to_csv(index=False), "aura_export.csv")

# --- PAGE : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Paramètres & Fichiers")
    with st.container(border=True):
        st.subheader("🔔 Notifications")
        profile.notify_discord = st.toggle("Activer Discord", value=profile.notify_discord)
        profile.discord_webhook = st.text_input("Webhook URL", value=profile.discord_webhook, type="password")
        if st.button("Enregistrer les préférences"):
            db.commit(); st.success("Préférences sauvegardées.")

    st.subheader("📁 Mes documents stockés")
    u_path = f"/app/storage/{user['username']}"
    if os.path.exists(u_path):
        for a_dir in os.listdir(u_path):
            acc_obj = db.get(Account, int(a_dir))
            st.write(f"**{acc_obj.bank_name if acc_obj else a_dir}**")
            for f_name in os.listdir(os.path.join(u_path, a_dir)):
                c1, c2 = st.columns([0.8, 0.2])
                c1.caption(f"📄 {f_name}")
                if c2.button("🗑️", key=f"f_del_{user['username']}_{a_dir}_{f_name}"):
                    os.remove(os.path.join(u_path, a_dir, f_name)); st.rerun()
    else:
        st.info("Aucun fichier sur le serveur.")

    st.divider()
    if st.button("🚨 RÉINITIALISER TOUTES MES DONNÉES", type="primary"):
        all_accs = db.query(Account).filter_by(user_id=user["username"]).all()
        for a in all_accs: db.delete(a)
        if os.path.exists(u_path): shutil.rmtree(u_path)
        db.commit(); st.rerun()

# --- PAGE : ADMIN ---
elif menu == "🛡️ Admin":
    st.header("🛡️ Administration Système")
    t1, t2 = st.tabs(["👥 Utilisateurs", "🗄️ Stockage Global"])
    
    with t1:
        for p in db.query(UserProfile).all():
            with st.container(border=True):
                ca, cb, cc = st.columns([0.2, 0.6, 0.2])
                ca.write(f"👤 **{p.username}**")
                pct = p.token_used / p.token_limit if p.token_limit > 0 else 0
                cb.progress(min(pct, 1.0), text=f"{p.token_used:,} / {p.token_limit:,} tokens")
                new_l = cc.number_input("Quota", value=p.token_limit, key=f"lim_{p.id}", step=10000)
                if new_l != p.token_limit:
                    p.token_limit = new_l; db.commit(); st.rerun()

    with t2:
        base_s = "/app/storage"
        if os.path.exists(base_s):
            for u_dir in os.listdir(base_s):
                st.write(f"👤 **Utilisateur : {u_dir}**")
                u_p = os.path.join(base_s, u_dir)
                if os.path.isdir(u_p):
                    for a_dir in os.listdir(u_p):
                        files = os.listdir(os.path.join(u_p, a_dir))
                        st.caption(f"    └─ Dossier Compte {a_dir} : {len(files)} fichiers")
        else:
            st.info("Stockage vide.")

db.close()
