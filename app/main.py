import streamlit as st
import pandas as pd
from database import SessionLocal, Account
from admin import admin_page
from modules.charts import render_patrimoine_chart

st.set_page_config(page_title="Aura Wealth", layout="wide", page_icon="🌌")

# --- AUTHENTICATION VIA AUTHELIA (NGINX HEADERS) ---
# En production derrière NPM, on lit le header HTTP
headers = st.context.headers
# Remplace "Remote-User" par le header exact configuré dans ton NPM/Authelia
current_user = headers.get("Remote-User", "dev_user") 
is_admin = current_user in ["loic", "admin"] # Liste des admins

st.sidebar.title(f"🌌 Aura Wealth")
st.sidebar.caption(f"Connecté en tant que : {current_user}")

# Navigation
pages = ["Vue Globale", "Mes Comptes", "Simulation"]
if is_admin:
    pages.append("🛡️ Administration")

selection = st.sidebar.radio("Menu", pages)

if selection == "Vue Globale":
    st.header("État de ton Patrimoine")
    # Appel de la fonction extensible
    render_patrimoine_chart(current_user)

elif selection == "🛡️ Administration":
    admin_page(current_user)
