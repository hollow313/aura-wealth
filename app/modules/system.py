import streamlit as st
import pandas as pd
import os, shutil
from sqlalchemy import func
from database import Account, BankAccount, UserProfile

def render_export(user, db):
    st.header("📑 Exportation complète de vos données")
    accs = db.query(Account).filter_by(user_id=user["username"]).all()
    bas = db.query(BankAccount).filter_by(user_id=user["username"]).all()
    
    st.subheader("1. Export Patrimonial (Investissements)")
    if accs:
        if st.button("📥 Exporter le Patrimoine", type="primary"):
            data = []
            for a in accs:
                for r in a.records:
                    data.append({
                        "Banque": a.bank_name, "Type de Compte": a.account_type, "Contrat/ID": a.contract_number,
                        "Devise": a.currency, "Saisie Manuelle": "Oui" if a.is_manual else "Non", "Date Relevé": r.date_releve,
                        "Valeur Totale": r.total_value, "Capital Versé": r.total_invested, "Valeur Fonds Euros": r.fonds_euro_value,
                        "Valeur Unités Compte": r.uc_value, "Primes / Dividendes": r.dividends
                    })
            st.download_button("Télécharger Patrimoine", pd.DataFrame(data).to_csv(index=False), "export_patrimoine.csv")
    else: st.warning("Aucune donnée patrimoniale à exporter.")

    st.divider()
    st.subheader("2. Export Budget (Comptes Courants)")
    if bas:
        if st.button("📥 Exporter le Budget", type="primary"):
            data_b = []
            for ba in bas:
                for t in ba.transactions:
                    data_b.append({
                        "Banque": ba.bank_name, "Compte": ba.account_name, "Date": t.date,
                        "Libellé": t.label, "Catégorie": t.category, "Montant": t.amount, "Solde": t.balance
                    })
            st.download_button("Télécharger Budget", pd.DataFrame(data_b).to_csv(index=False), "export_budget.csv")
    else: st.warning("Aucune transaction bancaire à exporter.")

def render_settings(user, profile, db):
    st.header("⚙️ Configuration")
    
    with st.container(border=True):
        st.subheader("💱 Devises affichées")
        curr = profile.active_currencies.split(",") if profile.active_currencies else ["EUR"]
        sel_c = st.multiselect("Sélectionnez les devises que vous utilisez", ["EUR", "CHF", "USD", "GBP", "CAD"], default=curr)
        
        st.divider()
        st.subheader("🔔 Notifications")
        profile.notify_discord = st.toggle("Activer les notifications Discord", profile.notify_discord)
        profile.discord_webhook = st.text_input("URL du Webhook Discord", profile.discord_webhook, type="password")
        
        if st.button("💾 Enregistrer les préférences", type="primary"): 
            profile.active_currencies = ",".join(sel_c)
            db.commit(); st.success("Paramètres enregistrés !")

    st.divider()
    with st.expander("🚨 Zone de danger - Réinitialisation Totale"):
        st.warning("Cette action effacera toutes vos données.")
        if st.checkbox("Je confirme vouloir tout supprimer."):
            if st.button("🗑️ EFFACER TOUTES MES DONNÉES", type="primary"):
                for a in db.query(Account).filter_by(user_id=user["username"]).all(): db.delete(a)
                for ba in db.query(BankAccount).filter_by(user_id=user["username"]).all(): db.delete(ba)
                u_path = f"/app/storage/{user['username']}"
                if os.path.exists(u_path): shutil.rmtree(u_path)
                db.commit(); db.close(); st.rerun()

def render_admin(db):
    st.header("🛡️ Administration Système")
    tot_jour = db.query(func.sum(UserProfile.token_used_daily)).scalar() or 0
    st.progress(min(tot_jour / 100000, 1.0), text=f"Consommation API Jour : {tot_jour:,} / 100,000 tokens")

    for p in db.query(UserProfile).all():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([0.2, 0.3, 0.3, 0.2])
            c1.write(f"👤 **{p.username}**")
            c2.write(f"📅 Conso Jour : {p.token_used_daily:,}")
            c3.write(f"🗓️ Conso Hebdo : {p.token_used_weekly:,} / {p.token_limit_weekly:,}")
            nl = c4.number_input("Quota Hebdo", value=p.token_limit_weekly, key=f"limit_{p.id}", step=10000)
            if nl != p.token_limit_weekly: 
                p.token_limit_weekly = nl; db.commit(); db.close(); st.rerun()
