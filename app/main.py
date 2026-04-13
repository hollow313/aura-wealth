import streamlit as st
import pandas as pd
import os
import shutil
from datetime import datetime

# --- IMPORTS INTERNES ---
from database import SessionLocal, Account, Record, GlobalSettings, UserProfile
from auth import get_user_info
from parser import check_quota_and_parse
from admin import admin_page
from modules.charts import render_patrimoine_chart, render_account_history
from modules.calcs import calculate_compound_interest

# --- CONFIGURATION ---
st.set_page_config(page_title="Aura Wealth", page_icon="🌌", layout="wide")

# --- CACHE DE L'ANALYSE IA ---
# Cette fonction mémorise le résultat pour éviter de payer/utiliser l'IA 50 fois pour le même PDF
@st.cache_data(show_spinner=False)
def cached_parse(file_content, file_name, api_key):
    # On crée un fichier temporaire pour le parser
    temp_path = f"/tmp/{file_name}"
    with open(temp_path, "wb") as f:
        f.write(file_content)
    
    result = check_quota_and_parse(temp_path, api_key)
    return result, temp_path

# --- AUTHENTIFICATION ---
user = get_user_info()
if not user["is_member"] and user["authenticated"]:
    st.error("🚫 Accès restreint.")
    st.stop()

db = SessionLocal()

# --- PROFIL ET PRÉFÉRENCES ---
if user["authenticated"]:
    profile = db.query(UserProfile).filter_by(username=user["username"]).first()
    if not profile:
        profile = UserProfile(username=user["username"], show_chf=False)
        db.add(profile)
        db.commit()
else:
    profile = UserProfile(username="DevMode", show_chf=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🌌 Aura")
    st.caption(f"Utilisateur : {user['username']}")
    st.divider()
    
    menu = st.radio("Navigation", ["🌍 Vue Globale", "💳 Mes Comptes", "🚀 Simulation", "🛡️ Admin"] if user["is_admin"] else ["🌍 Vue Globale", "💳 Mes Comptes", "🚀 Simulation"])
    
    st.divider()
    new_show_chf = st.toggle("🇨🇭 Devise Suisse (CHF)", value=profile.show_chf)
    if new_show_chf != profile.show_chf and user["authenticated"]:
        profile.show_chf = new_show_chf
        db.commit()
        st.rerun()

    # --- BOUTON WIPE DATA ---
    st.divider()
    st.subheader("⚠️ Zone de danger")
    if st.button("🚨 Réinitialiser mes données", type="primary"):
        st.session_state["confirm_wipe"] = True

    if st.session_state.get("confirm_wipe", False):
        st.warning("Tout supprimer définitivement ?")
        c1, c2 = st.columns(2)
        if c1.button("✔️ Oui"):
            accounts = db.query(Account).filter(Account.user_id == user["username"]).all()
            for a in accounts: db.delete(a)
            db.commit()
            if os.path.exists(f"/app/storage/{user['username']}"):
                shutil.rmtree(f"/app/storage/{user['username']}")
            st.session_state["confirm_wipe"] = False
            st.success("Données effacées.")
            st.rerun()
        if c2.button("❌ Non"):
            st.session_state["confirm_wipe"] = False
            st.rerun()

# --- PAGE : MES COMPTES ---
if menu == "💳 Mes Comptes":
    st.header("Gestion des Comptes")
    
    # ZONE D'UPLOAD
    uploaded_file = st.file_uploader("Ajouter un relevé PDF", type="pdf")
    
    if uploaded_file:
        # On vérifie si on a déjà traité ce fichier dans cette session
        if f"done_{uploaded_file.name}" not in st.session_state:
            with st.status("🔮 Analyse Aura IA en cours...", expanded=True) as status:
                # Appel de la fonction avec Cache
                result, temp_path = cached_parse(uploaded_file.getvalue(), uploaded_file.name, os.getenv("GEMINI_API_KEY"))
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    # Enregistrement en BDD
                    acc = db.query(Account).filter_by(user_id=user["username"], bank_name=result["bank_name"], account_type=result["account_type"]).first()
                    if not acc:
                        acc = Account(user_id=user["username"], bank_name=result["bank_name"], account_type=result["account_type"], currency=result["currency"])
                        db.add(acc); db.commit(); db.refresh(acc)

                    new_rec = Record(account_id=acc.id, date_releve=datetime.strptime(result["date"], "%Y-%m-%d"), total_value=result["total_value"])
                    db.add(new_rec)
                    
                    # Déplacement du fichier
                    save_dir = f"/app/storage/{user['username']}/{acc.id}"
                    os.makedirs(save_dir, exist_ok=True)
                    shutil.move(temp_path, f"{save_dir}/{result['date']}.pdf")
                    
                    db.commit()
                    st.session_state[f"done_{uploaded_file.name}"] = True
                    status.update(label="✅ Analyse terminée !", state="complete")
                    st.success("Données enregistrées.")
                    st.rerun()

    st.divider()

    # LISTE DES COMPTES AVEC BOUTON SUPPRIMER
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    for acc in accounts:
        with st.expander(f"📂 {acc.bank_name} - {acc.account_type}", expanded=True):
            col_info, col_del = st.columns([0.85, 0.15])
            col_info.write(f"Devise : **{acc.currency}**")
            if col_del.button("🗑️", key=f"del_{acc.id}", help="Supprimer ce compte"):
                db.delete(acc)
                db.commit()
                st.rerun()
            render_account_history(acc.id)

# --- PAGE : VUE GLOBALE ---
elif menu == "🌍 Vue Globale":
    st.header("Patrimoine Global")
    # ... (Garde ton code précédent pour le calcul des totaux ici)
    render_patrimoine_chart(user["username"])

# --- PAGE : SIMULATION ---
elif menu == "🚀 Simulation":
    st.header("Simulateur")
    # ... (Garde ton code précédent de simulation ici)

elif menu == "🛡️ Admin":
    admin_page(user["username"])

db.close()
