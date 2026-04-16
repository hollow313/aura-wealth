import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from database import BankAccount, BankTransaction
from utils import safe_float, categorize_transaction
from modules.charts import render_budget_pie, render_balance_history, render_expenses_bar_chart

def render_budget(user, profile, db):
    st.header("💸 Gestion du Quotidien (Import CSV)")
    # Correction de la variable manquante (t_manage)
    t_dash, t_import, t_manage = st.tabs(["📊 Synthèse & Filtres", "📥 Import CSV (Local)", "📂 Gérer mes comptes"])
    
    bank_accounts = db.query(BankAccount).filter_by(user_id=user["username"]).all()

    # --- SYNTHESE & FILTRES EXPERTS ---
    with t_dash:
        if not bank_accounts:
            st.info("Aucune donnée. Importez un fichier CSV bancaire pour commencer.")
        else:
            # 1. Extraction de toutes les données brutes
            raw_tx = []
            for ba in bank_accounts: raw_tx.extend(ba.transactions)
            
            if raw_tx:
                # Création d'un DataFrame Pandas pour faciliter les filtres
                df_all = pd.DataFrame([{
                    "Compte": t.account.account_name, 
                    "Date": pd.to_datetime(t.date), 
                    "Libellé": t.label,
                    "Catégorie": t.category, 
                    "Montant (€)": t.amount, 
                    "Solde": t.balance
                } for t in raw_tx])

                # --- BARRE DE FILTRES ---
                st.markdown("### 🔍 Filtres d'Analyse")
                with st.container(border=True):
                    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                    
                    # Filtre 1 : Date
                    date_filter = f_col1.selectbox("Période", ["Toutes", "Mois en cours", "Le mois dernier", "Cette année", "Personnalisée"])
                    start_date, end_date = df_all["Date"].min(), df_all["Date"].max()
                    
                    now = datetime.now()
                    if date_filter == "Mois en cours":
                        start_date = datetime(now.year, now.month, 1)
                    elif date_filter == "Le mois dernier":
                        first_day_this_month = datetime(now.year, now.month, 1)
                        end_date = first_day_this_month - timedelta(days=1)
                        start_date = datetime(end_date.year, end_date.month, 1)
                    elif date_filter == "Cette année":
                        start_date = datetime(now.year, 1, 1)
                    elif date_filter == "Personnalisée":
                        dates = f_col1.date_input("Sélectionnez la plage", [start_date, end_date])
                        if len(dates) == 2: start_date, end_date = pd.to_datetime(dates[0]), pd.to_datetime(dates[1])
                    
                    # Filtre 2 : Compte
                    acc_list = ["Tous"] + df_all["Compte"].unique().tolist()
                    acc_filter = f_col2.selectbox("Compte Bancaire", acc_list)
                    
                    # Filtre 3 : Type d'opération
                    type_filter = f_col3.selectbox("Type", ["Tous", "Dépenses (Débit)", "Revenus (Crédit)"])
                    
                    # Filtre 4 : Catégorie
                    cat_list = ["Toutes"] + sorted(df_all["Catégorie"].unique().tolist())
                    cat_filter = f_col4.selectbox("Catégorie", cat_list)

                # --- APPLICATION DES FILTRES ---
                mask = (df_all["Date"] >= pd.to_datetime(start_date)) & (df_all["Date"] <= pd.to_datetime(end_date))
                if acc_filter != "Tous": mask &= (df_all["Compte"] == acc_filter)
                if type_filter == "Dépenses (Débit)": mask &= (df_all["Montant (€)"] < 0)
                elif type_filter == "Revenus (Crédit)": mask &= (df_all["Montant (€)"] > 0)
                if cat_filter != "Toutes": mask &= (df_all["Catégorie"] == cat_filter)
                
                df_filtered = df_all[mask].copy()

                # --- AFFICHAGE DES KPIS ---
                if not df_filtered.empty:
                    total_in = df_filtered[df_filtered["Montant (€)"] > 0]["Montant (€)"].sum()
                    total_out = df_filtered[df_filtered["Montant (€)"] < 0]["Montant (€)"].sum()
                    
                    st.markdown(f"**Résultats pour la période du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}**")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("🟢 Total des Entrées", f"{total_in:,.2f} €")
                    col2.metric("🔴 Total des Dépenses", f"{abs(total_out):,.2f} €")
                    col3.metric("⚖️ Capacité d'Épargne (Balance)", f"{(total_in + total_out):,.2f} €")
                    
                    st.divider()
                    
                    # --- GRAPHIQUES ---
                    # On recrée une liste d'objets factices pour réutiliser les fonctions de chart existantes
                    class DummyTx:
                        def __init__(self, cat, amt, dt, bal):
                            self.category = cat
                            self.amount = amt
                            self.date = dt
                            self.balance = bal
                    
                    chart_data = [DummyTx(row["Catégorie"], row["Montant (€)"], row["Date"], row["Solde"]) for _, row in df_filtered.iterrows()]

                    c_left, c_right = st.columns(2)
                    with c_left:
                        st.subheader("Top Catégories (Dépenses)")
                        render_expenses_bar_chart(chart_data)
                    with c_right:
                        st.subheader("Évolution du Solde")
                        render_balance_history(chart_data)
                    
                    st.divider()
                    
                    # --- TABLEAU DE DONNEES AVEC TRI ---
                    st.subheader("Historique des transactions")
                    st.caption("💡 Vous pouvez cliquer sur l'en-tête d'une colonne (ex: 'Montant') pour trier les données du plus grand au plus petit.")
                    
                    # Formatage des dates pour l'affichage propre
                    df_filtered["Date"] = df_filtered["Date"].dt.strftime('%Y-%m-%d')
                    
                    def color_amount(val):
                        color = '#10b981' if val > 0 else '#ef4444'
                        return f'color: {color}; font-weight: bold'
                    
                    styled_df = df_filtered.style.applymap(color_amount, subset=['Montant (€)']).format({'Montant (€)': "{:.2f} €", 'Solde': "{:.2f} €"})
                    st.dataframe(styled_df, hide_index=True, use_container_width=True)
                else:
                    st.warning("Aucune transaction ne correspond à ces filtres.")

    # --- IMPORT CSV (MISE A JOUR INCREMENTALE) ---
    with t_import:
        st.info("Les fichiers CSV sont traités localement. Le système ignore automatiquement les doublons pour ne rajouter que les lignes manquantes.")
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
                        
                        if st.form_submit_button("💾 Importer les nouvelles lignes", type="primary"):
                            try:
                                ba_id = opts[target_ba]
                                if ba_id == "NEW":
                                    if not b_name or not a_name:
                                        st.error("Veuillez renseigner le nom de la banque et du compte.")
                                        st.stop()
                                    new_ba = BankAccount(user_id=user["username"], bank_name=b_name, account_name=a_name)
                                    db.add(new_ba); db.commit(); db.refresh(new_ba); ba_id = new_ba.id
                                
                                count = 0
                                ignored = 0
                                for idx, row in df.iterrows():
                                    try:
                                        # Gestion tolérante des formats de date (ex: 15/11/2022 ou 2022-11-15)
                                        try: d_val = pd.to_datetime(row[date_col], format='%d/%m/%Y').date()
                                        except: d_val = pd.to_datetime(row[date_col]).date()
                                        
                                        a_val = safe_float(row[amount_col])
                                        l_val = str(row[label_col])[:255]
                                        bal_val = safe_float(row[balance_col]) if balance_col else None
                                        cat_val = categorize_transaction(l_val, a_val)
                                        
                                        # VERIFICATION ANTI-DOUBLON
                                        # On vérifie si une ligne avec la même date, le même montant exact et le même libellé existe déjà
                                        exist = db.query(BankTransaction).filter_by(account_id=ba_id, date=d_val, amount=a_val, label=l_val).first()
                                        if not exist:
                                            db.add(BankTransaction(account_id=ba_id, date=d_val, amount=a_val, label=l_val, balance=bal_val, category=cat_val))
                                            count += 1
                                        else:
                                            ignored += 1
                                    except Exception as line_e: pass 
                                
                                db.commit()
                                st.toast(f"✅ {count} lignes importées ! ({ignored} doublons ignorés)", icon="🎉")
                                db.close(); st.rerun()
                            except Exception as err:
                                db.rollback(); st.error(f"Erreur d'insertion : {err}")
                else:
                    st.error("Impossible de détecter les colonnes Date, Montant et Libellé.")
            except Exception as e:
                st.error(f"Erreur de lecture du fichier CSV : {e}")

    # --- GESTION (SUPPRESSION CIBLEE) ---
    with t_manage:
        st.info("La suppression d'un compte ici n'affecte QUE ce compte. Vos autres données restent intactes.")
        for ba in bank_accounts:
            with st.expander(f"🏦 {ba.bank_name} - {ba.account_name}"):
                st.write(f"Nombre de transactions enregistrées : **{len(ba.transactions)}**")
                if st.button("🗑️ Supprimer uniquement ce compte", key=f"del_ba_{ba.id}"):
                    db.delete(ba); db.commit(); db.close(); st.rerun()
