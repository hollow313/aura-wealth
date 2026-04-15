import streamlit as st
import os, shutil, pandas as pd
from datetime import datetime
from database import SessionLocal, Account, Record, UserProfile
from parser import check_quota_and_parse
from modules.charts import render_patrimoine_chart, render_account_history

st.set_page_config(page_title="Aura Wealth Pro", layout="wide")

# --- PERSISTANCE (CONSEIL TRUENAS) ---
# Assure-toi que le dossier /app/storage est monté sur un Dataset TrueNAS
# pour que le fichier aura_db (SQLite) ou tes PDFs ne disparaissent pas.

user = get_user_info()
db = SessionLocal()

# --- PAGE : DASHBOARD ---
if menu == "🌍 Dashboard":
    st.header("📈 Dashboard Patrimonial")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if accounts:
        investi_total = sum(a.total_invested for a in accounts)
        actuel_total = 0
        dividendes_total = 0
        
        perf_rows = []
        for a in accounts:
            if a.records:
                last_rec = sorted(a.records, key=lambda r: r.date_releve)[-1]
                actuel_total += last_rec.total_value
                dividendes_total += sum(r.dividends for r in a.records)
                
                plus_value_eur = last_rec.total_value - a.total_invested
                perf_pct = (plus_value_eur / a.total_invested * 100) if a.total_invested > 0 else 0
                
                perf_rows.append({
                    "Compte": f"{a.bank_name} ({a.account_type})",
                    "Capital Investi": f"{a.total_invested:,.2f} €",
                    "Valeur Actuelle": f"{last_rec.total_value:,.2f} €",
                    "Plus-Value": f"{plus_value_eur:+.2f} €",
                    "Rendement": f"{perf_pct:+.2f}%"
                })

        # Affichage des Métriques
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Investi", f"{investi_total:,.0f} €")
        c2.metric("Valeur Marché", f"{actuel_total:,.2f} €")
        pv_globale = actuel_total - investi_total
        c3.metric("Plus-Value Globale", f"{pv_globale:+.2f} €", f"{(pv_globale/investi_total*100):+.2f}%" if investi_total > 0 else None)
        c4.metric("Dividendes", f"{dividendes_total:,.2f} €")

        st.divider()
        st.subheader("Détail par portefeuille")
        st.dataframe(pd.DataFrame(perf_rows), hide_index=True, use_container_width=True)
        render_patrimoine_chart(accounts)

# --- MISE À JOUR LORS DE L'IMPORT ---
# Dans la section "Confirmer l'import" de Mes Comptes, ajoute ceci :
if st.button("✅ Confirmer l'import"):
    # ... (code précédent)
    acc.total_invested = res['total_invested'] # On met à jour le capital investi lu par l'IA
    db.commit()
