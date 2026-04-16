import streamlit as st
from database import SessionLocal, UserProfile
from auth import get_user_info
from fix_db import migrate

# --- IMPORTS DES NOUVEAUX MODULES ---
from utils import manage_token_resets
from modules.dashboard import render_dashboard
from modules.patrimoine import render_patrimoine
from modules.budget import render_budget
from modules.system import render_export, render_settings, render_admin

st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

# --- INITIALISATION ---
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
        profile = UserProfile(username=user["username"])
        db.add(profile); db.commit(); db.refresh(profile)

    manage_token_resets(profile, db)

    # --- MENU DE NAVIGATION ---
    with st.sidebar:
        st.title("🌌 Aura Pro")
        st.write(f"Utilisateur : **{user['username']}**")
        
        pages = ["🌍 Dashboard", "💳 Patrimoine & PDF", "💸 Budget & Dépenses", "📑 Export", "⚙️ Paramètres"]
        if user.get("is_admin"): pages.append("🛡️ Admin")
        
        menu = st.radio("Navigation", pages)
        
        st.divider()
        st.subheader("📅 Quota IA Hebdomadaire")
        u_pct = (profile.token_used_weekly / profile.token_limit_weekly) if profile.token_limit_weekly > 0 else 0
        st.progress(min(max(u_pct, 0.0), 1.0), text=f"{profile.token_used_weekly:,} / {profile.token_limit_weekly:,}")

    # --- ROUTAGE DES PAGES ---
    if menu == "🌍 Dashboard":
        render_dashboard(user, profile, db)
    elif menu == "💳 Patrimoine & PDF":
        render_patrimoine(user, profile, db)
    elif menu == "💸 Budget & Dépenses":
        render_budget(user, profile, db)
    elif menu == "📑 Export":
        render_export(user, db)
    elif menu == "⚙️ Paramètres":
        render_settings(user, profile, db)
    elif menu == "🛡️ Admin":
        render_admin(db)

# --- SÉCURITÉ GARANTIE (Zéro Fuite de Mémoire) ---
finally:
    db.close()
