import streamlit as st
import pandas as pd
import os
import shutil  # <--- Ajoute cette ligne ici
from datetime import datetime

# --- IMPORTS INTERNES ---
from database import SessionLocal, Account, Record, GlobalSettings, UserProfile
from auth import get_user_info
from parser import check_quota_and_parse
from admin import admin_page
from modules.charts import render_patrimoine_chart, render_account_history
from modules.calcs import calculate_compound_interest

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Aura Wealth",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DESIGN "AURA 2026" (CSS CUSTOM) ---
st.markdown("""
    <style>
    /* Fond et dégradés typés 2026 */
    .stApp {
        background: radial-gradient(circle at top right, #1e1b4b, #0f172a);
    }
    
    /* Cartes Glassmorphism */
    div[data-testid="metric-container"] {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(99, 102, 241, 0.2);
        padding: 15px;
        border-radius: 15px;
        backdrop-filter: blur(10px);
    }

    /* Style des titres */
    h1, h2, h3 {
        color: #f8fafc !important;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
    }

    /* Boutons personnalisés */
    .stButton>button {
        border-radius: 12px;
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
    }
    </style>
    """, unsafe_allow_html=True)

# --- GESTION DE L'AUTHENTIFICATION ---
user = get_user_info()

if not user["is_member"] and user["authenticated"]:
    st.title("🌌 Aura Wealth")
    st.error("🚫 Accès restreint. Vous devez faire partie du groupe 'assurance-vie' pour accéder aux données.")
    st.stop()

db = SessionLocal()

# --- GESTION DU PROFIL UTILISATEUR ---
if user["authenticated"]:
    # On cherche ou on crée le profil pour sauvegarder les préférences (ex: CHF)
    profile = db.query(UserProfile).filter_by(username=user["username"]).first()
    if not profile:
        profile = UserProfile(username=user["username"], show_chf=False)
        db.add(profile)
        db.commit()
else:
    profile = UserProfile(username="DevMode", show_chf=True)

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("🌌 Aura")
    st.caption(f"Connecté : {user['username']}")
    st.divider()
    
    # Menu dynamique selon les droits
    menu = st.radio(
        "Navigation",
        ["🌍 Vue Globale", "💳 Mes Comptes", "🚀 Simulation", "🛡️ Admin"] if user["is_admin"] 
        else ["🌍 Vue Globale", "💳 Mes Comptes", "🚀 Simulation"]
    )
    
    st.divider()
    
    # --- ZONE DE DANGER : WIPE DATA ---
    st.markdown("### ⚠️ Zone de danger")
    if st.button("🚨 Réinitialiser mes données", type="primary"):
        st.session_state["confirm_wipe"] = True

    if st.session_state.get("confirm_wipe", False):
        st.warning("Cela supprimera DÉFINITIVEMENT tous vos comptes et PDF.")
        col_yes, col_no = st.columns(2)
        if col_yes.button("✔️ Confirmer"):
            # 1. Nettoyage de la base de données
            accounts = db.query(Account).filter(Account.user_id == user["username"]).all()
            for acc in accounts:
                db.delete(acc) # Grâce au "cascade=all", les records sont aussi effacés
            db.commit()
            
            # 2. Nettoyage des PDF physiques stockés sur TrueNAS
            user_dir = f"/app/storage/{user['username']}"
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
            
            st.session_state["confirm_wipe"] = False
            st.success("Toutes vos données ont été effacées.")
            st.rerun()
            
        if col_no.button("❌ Annuler"):
            st.session_state["confirm_wipe"] = False
            st.rerun()
    
    # Bouton d'activation du Franc Suisse (sauvegardé en BDD)
    new_show_chf = st.toggle("🇨🇭 Devise Suisse (CHF)", value=profile.show_chf)
    if new_show_chf != profile.show_chf and user["authenticated"]:
        profile.show_chf = new_show_chf
        db.commit()
        st.rerun()
        
    st.divider()
    
    # Bouton d'export des données
    if st.button("📥 Exporter en CSV"):
        data = db.query(Record).join(Account).filter(Account.user_id == user["username"]).all()
        df_export = pd.DataFrame([{
            "Date": r.date_releve, 
            "Banque": r.account.bank_name,
            "Type": r.account.account_type,
            "Valeur": r.total_value,
            "Devise": r.account.currency
        } for r in data])
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button("Confirmer le téléchargement", data=csv, file_name=f"aura_export_{user['username']}.csv")

# --- LOGIQUE DES PAGES ---

if menu == "🌍 Vue Globale":
    st.header("État de ton Patrimoine")
    
    # Récupération du taux de change
    settings = db.query(GlobalSettings).first()
    chf_rate = settings.chf_eur_rate if settings else 1.03
    
    # Calcul des totaux
    accounts = db.query(Account).filter(Account.user_id == user["username"]).all()
    total_eur = 0
    total_chf = 0
    
    for acc in accounts:
        # On prend la dernière valeur connue pour chaque compte
        last_record = db.query(Record).filter(Record.account_id == acc.id).order_by(Record.date_releve.desc()).first()
        if last_record:
            if acc.currency == "EUR":
                total_eur += last_record.total_value
            else:
                total_chf += last_record.total_value

    # Affichage conditionnel selon le toggle CHF
    if profile.show_chf:
        total_consolidated = total_eur + (total_chf * chf_rate)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Consolidé (€)", f"{total_consolidated:,.2f} €")
        col2.metric("Part en Euros", f"{total_eur:,.2f} €")
        col3.metric("Part en Francs Suisses", f"{total_chf:,.2f} CHF", delta=f"Taux: {chf_rate:.4f}")
    else:
        st.metric("Total Patrimoine (€)", f"{total_eur:,.2f} €")

    st.divider()
    render_patrimoine_chart(user["username"])

elif menu == "💳 Mes Comptes":
    st.header("Gestion des Comptes")
    
    # 1. ZONE D'UPLOAD ET ANALYSE IA
    with st.expander("➕ Ajouter un nouveau relevé (PDF)"):
        uploaded_file = st.file_uploader("Glissez votre document ici", type="pdf")
        if uploaded_file:
            temp_path = f"/tmp/{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            with st.spinner("Analyse Aura IA en cours..."):
                # Envoi à l'API Gemini
                result = check_quota_and_parse(temp_path, os.getenv("GEMINI_API_KEY"))
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    # Recherche du compte ou création
                    acc = db.query(Account).filter(
                        Account.user_id == user["username"],
                        Account.bank_name == result["bank_name"],
                        Account.account_type == result["account_type"]
                    ).first()
                    
                    if not acc:
                        acc = Account(
                            user_id=user["username"],
                            bank_name=result["bank_name"],
                            account_type=result["account_type"],
                            currency=result["currency"]
                        )
                        db.add(acc)
                        db.commit()
                        db.refresh(acc)

                    # Ajout de l'enregistrement temporel
                    new_rec = Record(
                        account_id=acc.id,
                        date_releve=datetime.strptime(result["date"], "%Y-%m-%d"),
                        total_value=result["total_value"]
                    )
                    db.add(new_rec)
                    
                    # Sauvegarde physique du PDF dans le dossier bindé TrueNAS
                    save_dir = f"/app/storage/{user['username']}/{acc.id}"
                    os.makedirs(save_dir, exist_ok=True)
                    shutil.move(temp_path, f"{save_dir}/{result['date']}.pdf")
                    
                    db.commit()
                    st.success(f"Relevé {result['bank_name']} ajouté avec succès !")
                    st.rerun()

    # 2. AFFICHAGE DE L'HISTORIQUE DES COMPTES
    accounts = db.query(Account).filter(Account.user_id == user["username"]).all()
    for acc in accounts:
        with st.container():
            st.subheader(f"{acc.bank_name} - {acc.account_type}")
            render_account_history(acc.id)

elif menu == "🚀 Simulation":
    st.header("Simulateur de Croissance")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Paramètres")
        capital_init = st.number_input("Capital Actuel (€)", value=35000)
        mensuel = st.slider("Versement mensuel (€)", 0, 5000, 600)
        duree = st.slider("Horizon (Années)", 1, 40, 10)
        rendement = st.slider("Rendement annuel estimé (%)", 0.0, 12.0, 5.0)
        
    with col2:
        st.subheader("Projection")
        projection_data = calculate_compound_interest(capital_init, mensuel, duree, rendement/100)
        df_proj = pd.DataFrame(projection_data)
        
        st.line_chart(df_proj.set_index("Année")[["Valeur Estimée", "Capital Versé"]])
        
        final_val = projection_data[-1]["Valeur Estimée"]
        st.info(f"Capital estimé dans {duree} ans : **{final_val:,.2f} €**")

elif menu == "🛡️ Admin":
    admin_page(user["username"])

# --- NETTOYAGE ---
db.close()
