import streamlit as st
import pandas as pd
import io
from datetime import datetime
from database import BankAccount, BankTransaction
from utils import safe_float, categorize_transaction
from modules.charts import render_budget_pie, render_balance_history

def render_budget(user, profile, db):
    st.header("💸 Gestion du Quotidien (Import CSV)")
    t_dash, t_import, t_manage = st.tabs(["📊 Synthèse & Courbes", "📥 Import CSV (Local)", "📂 Liste des Comptes"])
    
    bank_accounts = db.query(BankAccount).filter_by(user_id=user["username"]).all()

    # --- SYNTHESE ---
    with t_dash:
        if not bank_accounts:
            st.info("Aucune donnée. Importez un fichier CSV bancaire pour commencer.")
        else:
            all_tx = []
            for ba in bank_accounts: all_tx.extend(ba.transactions)
            
            if all_tx:
                c_left, c_right = st.columns(2)
                with c_left:
                    st.subheader("Où va mon argent ?")
                    render_budget_pie(all_tx)
                with c_right:
                    st.subheader("Évolution du Solde")
                    render_balance_history(all_tx)
                
                st.divider()
                st.subheader("Historique des transactions")
                df_tx = pd.DataFrame([{
                    "Compte": t.account.account_name, "Date": t.date, "Libellé": t.label,
                    "Catégorie": t.category, "Montant (€)": t.amount, "Solde": t.balance
                } for t in all_tx]).sort_values("Date", ascending=False)
                st.dataframe(df_tx, hide_index=True, use_container_width=True)

    # --- IMPORT CSV ---
    with t_import:
        st.info("Les fichiers CSV sont traités localement, instantanément et sans utiliser l'IA.")
        up_csv = st.file_uploader("Fichier CSV Bancaire", type=["csv", "txt", "tsv"])
        
        if up_csv:
            try:
                raw_data = up_csv.getvalue()
                sep = ';' if b';' in raw_data else (b'\t' if b'\t' in raw_data else ',')
                
                try: df = pd.read_csv(io.BytesIO(raw_data), sep=sep, decimal=',', encoding='utf-8', on_bad_lines='skip')
                except UnicodeDecodeError: df = pd.read_csv(io.BytesIO(raw_data), sep=sep, decimal=',', encoding='latin-1', on_bad_lines='skip')
                
                cols = df.columns.tolist()
                date_col = next((c for c in cols if 'date' in c.lower() and 'valeur' not in c.lower()), cols[0])
                amount_col = next((c for c in cols if 'montant' in c.lower() or 'débit' in c.lower()), cols[2] if len(cols)>2 else None)
                label_col = next((c for c in cols if 'libellé' in c.lower() or 'opération' in c.lower()), cols[3] if len(cols)>3 else None)
                balance_col = next((c for c in cols if 'solde' in c.lower()), cols[4] if len(cols)>4 else None)

                if amount_col and label_col:
                    st.success("✅ Fichier reconnu.")
                    st.dataframe(df[[date_col, amount_col, label_col]].head(3), hide_index=True)
                    
                    with st.form("csv_import_form", border=True):
                        c1, c2 = st.columns(2)
                        b_name = c1.text_input("Banque (ex: Caisse d'Epargne)")
                        a_name = c2.text_input("Nom du compte (ex: Compte Courant)")
                        
                        opts = {f"{ba.bank_name} - {ba.account_name}": ba.id for ba in bank_accounts}
                        opts["➕ Créer ce nouveau compte"] = "NEW"
                        target_ba = st.selectbox("Assigner à", options=opts.keys())
                        
                        if st.form_submit_button("💾 Importer toutes les lignes", type="primary"):
                            try:
                                ba_id = opts[target_ba]
                                if ba_id == "NEW":
                                    if not b_name or not a_name:
                                        st.error("Veuillez renseigner le nom de la banque et du compte.")
                                        st.stop()
                                    new_ba = BankAccount(user_id=user["username"], bank_name=b_name, account_name=a_name)
                                    db.add(new_ba); db.commit(); db.refresh(new_ba); ba_id = new_ba.id
                                
                                count = 0
                                for idx, row in df.iterrows():
                                    try:
                                        d_val = pd.to_datetime(row[date_col], dayfirst=True).date()
                                        a_val = safe_float(row[amount_col])
                                        l_val = str(row[label_col])[:255]
                                        bal_val = safe_float(row[balance_col]) if balance_col else None
                                        cat_val = categorize_transaction(l_val, a_val)
                                        
                                        exist = db.query(BankTransaction).filter_by(account_id=ba_id, date=d_val, amount=a_val, label=l_val).first()
                                        if not exist:
                                            db.add(BankTransaction(account_id=ba_id, date=d_val, amount=a_val, label=l_val, balance=bal_val, category=cat_val))
                                            count += 1
                                    except: pass 
                                
                                db.commit()
                                st.toast(f"✅ {count} transactions importées !", icon="🎉")
                                db.close(); st.rerun()
                            except Exception as err:
                                db.rollback(); st.error(f"Erreur d'insertion : {err}")
                else:
                    st.error("Impossible de détecter les colonnes.")
            except Exception as e:
                st.error(f"Erreur de lecture du fichier CSV : {e}")

    # --- GESTION ---
    with t_budget_manage:
        for ba in bank_accounts:
            with st.expander(f"🏦 {ba.bank_name} - {ba.account_name}"):
                st.write(f"Nombre de transactions : **{len(ba.transactions)}**")
                if st.button("🗑️ Supprimer l'historique complet", key=f"del_ba_{ba.id}"):
                    db.delete(ba); db.commit(); db.close(); st.rerun()
