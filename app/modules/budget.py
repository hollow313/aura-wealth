import streamlit as st
import pandas as pd
import io
from datetime import datetime
import plotly.express as px
from database import BankAccount, BankTransaction, CategoryRule

def init_default_rules(user_id, db):
    """Initialise des règles par défaut si l'utilisateur n'en a pas encore"""
    existing = db.query(CategoryRule).filter_by(user_id=user_id).first()
    if not existing:
        defaults = {
            "Achats & E-commerce": "AMAZON, PAYPAL, CDISCOUNT, FNAC, DARTY, ALIEXPRESS",
            "Alimentation": "AUCHAN, CARREFOUR, LECLERC, INTERMARCHE, LIDL, ALDI, MONOPRIX",
            "Transports & Auto": "TOTAL, ESSO, SHELL, SNCF, UBER, VINCI, PEAGE",
            "Logement & Énergies": "EDF, ENGIE, EAU, LOYER, VEOLIA",
            "Abonnements": "NETFLIX, SPOTIFY, ORANGE, FREE, BOUYGUES, SFR, APPLE",
            "Santé": "PHARMACIE, CPAM, MUTUELLE, WILLIS, HOPITAL",
            "Restaurants": "UBER EATS, DELIVEROO, MCDO, RESTAURANT, BAKERY, CREPERIE",
            "Salaire & Revenus": "SALAIRE, PAIE, REMUNERATION, VIR WILLIS"
        }
        for cat, kw in defaults.items():
            db.add(CategoryRule(user_id=user_id, category_name=cat, keywords=kw))
        db.commit()

def auto_categorize(label, rules):
    """Assigne une catégorie en fonction des règles"""
    lbl = str(label).upper()
    for rule in rules:
        keywords = [k.strip().upper() for k in rule.keywords.split(",") if k.strip()]
        if any(k in lbl for k in keywords):
            return rule.category_name
    return "Autre / Non catégorisé"

def render_budget_tab(user_id, db):
    st.header("💸 Gestion du Quotidien (Comptes Courants)")
    
    init_default_rules(user_id, db)
    bank_accounts = db.query(BankAccount).filter_by(user_id=user_id).all()
    
    t_dash, t_import, t_rules, t_manage = st.tabs(["📊 Synthèse", "📥 Import CSV", "⚙️ Règles de Catégorisation", "📂 Gérer les Comptes"])
    
    # ONGLET SYNTHESE
    with t_dash:
        if not bank_accounts:
            st.info("Aucune donnée. Importez un fichier CSV pour commencer.")
        else:
            all_tx = []
            for ba in bank_accounts: all_tx.extend(ba.transactions)
            
            if all_tx:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("Répartition des dépenses")
                    expenses = [t for t in all_tx if t.amount < 0]
                    if expenses:
                        df_exp = pd.DataFrame([{"Catégorie": t.category, "Montant": abs(t.amount)} for t in expenses])
                        fig1 = px.pie(df_exp.groupby("Catégorie").sum().reset_index(), values='Montant', names='Catégorie', hole=0.5)
                        fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"))
                        st.plotly_chart(fig1, use_container_width=True)
                with c2:
                    st.subheader("Évolution du Solde")
                    valid_tx = [t for t in all_tx if t.balance is not None]
                    if valid_tx:
                        df_bal = pd.DataFrame([{"Date": t.date, "Solde": t.balance} for t in valid_tx]).sort_values("Date")
                        fig2 = px.line(df_bal, x="Date", y="Solde", line_shape="step")
                        fig2.update_traces(line_color="#14b8a6")
                        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"))
                        st.plotly_chart(fig2, use_container_width=True)
                
                st.divider()
                st.subheader("Historique Complet")
                df_tx = pd.DataFrame([{
                    "Compte": t.account.account_name, "Date": t.date, "Libellé": t.label,
                    "Catégorie": t.category, "Montant": t.amount, "Solde": t.balance
                } for t in all_tx]).sort_values("Date", ascending=False)
                st.dataframe(df_tx, hide_index=True, use_container_width=True)

    # ONGLET IMPORT CSV
    with t_import:
        st.info("Le fichier CSV est traité localement et instantanément (Aucune IA utilisée ici).")
        up_csv = st.file_uploader("Fichier CSV Bancaire", type=["csv"])
        
        if up_csv:
            try:
                # Lecture spécifique pour format français (séparateur ; et virgule pour décimales)
                df = pd.read_csv(up_csv, sep=';', decimal=',', encoding='utf-8', on_bad_lines='skip')
                
                cols = df.columns.tolist()
                date_col = next((c for c in cols if 'date' in c.lower() and 'valeur' not in c.lower()), cols[0])
                amount_col = next((c for c in cols if 'montant' in c.lower()), cols[2])
                label_col = next((c for c in cols if 'libellé' in c.lower() or 'opération' in c.lower()), cols[3])
                balance_col = next((c for c in cols if 'solde' in c.lower()), cols[4] if len(cols)>4 else None)

                st.success("✅ Fichier reconnu. Aperçu :")
                st.dataframe(df[[date_col, amount_col, label_col]].head(3), hide_index=True)
                
                with st.form("csv_import"):
                    c1, c2 = st.columns(2)
                    b_name = c1.text_input("Nom de la Banque (ex: Boursorama)")
                    a_name = c2.text_input("Nom du compte (ex: Compte Courant)")
                    
                    opts = {f"{ba.bank_name} - {ba.account_name}": ba.id for ba in bank_accounts}
                    opts["➕ Créer ce nouveau compte"] = "NEW"
                    target_ba = st.selectbox("Assigner à", options=opts.keys())
                    
                    if st.form_submit_button("💾 Importer", type="primary"):
                        rules = db.query(CategoryRule).filter_by(user_id=user_id).all()
                        ba_id = opts[target_ba]
                        if ba_id == "NEW":
                            if not b_name or not a_name:
                                st.error("Remplissez la banque et le compte.")
                                st.stop()
                            new_ba = BankAccount(user_id=user_id, bank_name=b_name, account_name=a_name)
                            db.add(new_ba); db.commit(); db.refresh(new_ba); ba_id = new_ba.id
                        
                        count = 0
                        for _, row in df.iterrows():
                            try:
                                d_val = pd.to_datetime(row[date_col], format='%d/%m/%Y', errors='coerce').date()
                                a_val = float(row[amount_col])
                                l_val = str(row[label_col])[:255]
                                bal_val = float(row[balance_col]) if balance_col and pd.notna(row[balance_col]) else None
                                cat_val = auto_categorize(l_val, rules)
                                
                                # Vérifie si la transaction existe déjà (éviter les doublons)
                                exist = db.query(BankTransaction).filter_by(account_id=ba_id, date=d_val, amount=a_val, label=l_val).first()
                                if not exist:
                                    db.add(BankTransaction(account_id=ba_id, date=d_val, amount=a_val, label=l_val, balance=bal_val, category=cat_val))
                                    count += 1
                            except: pass
                        
                        db.commit()
                        st.toast(f"✅ {count} nouvelles transactions importées !", icon="🎉")
                        st.rerun()
            except Exception as e:
                st.error(f"Erreur de lecture : Vérifiez que c'est bien un CSV avec séparateur point-virgule. Détail: {e}")

    # ONGLET REGLES DE CATEGORISATION
    with t_rules:
        st.write("Définissez des mots-clés. Si un libellé bancaire contient un de ces mots, il sera automatiquement classé dans la catégorie correspondante.")
        rules = db.query(CategoryRule).filter_by(user_id=user_id).all()
        
        with st.form("add_rule"):
            st.subheader("➕ Nouvelle Règle")
            c1, c2 = st.columns([1, 2])
            n_cat = c1.text_input("Nom de la catégorie (ex: Assurance Voiture)")
            n_kw = c2.text_input("Mots-clés (séparés par des virgules) (ex: ALLIANZ, AXA)")
            if st.form_submit_button("Ajouter la règle"):
                if n_cat and n_kw:
                    db.add(CategoryRule(user_id=user_id, category_name=n_cat, keywords=n_kw))
                    db.commit(); st.rerun()

        st.divider()
        for r in rules:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 0.5])
                c1.write(f"**{r.category_name}**")
                c2.write(f"`{r.keywords}`")
                if c3.button("🗑️ Supprimer", key=f"del_r_{r.id}"):
                    db.delete(r); db.commit(); st.rerun()

    # ONGLET GESTION
    with t_manage:
        if not bank_accounts: st.write("Aucun compte enregistré.")
        for ba in bank_accounts:
            with st.expander(f"🏦 {ba.bank_name} - {ba.account_name}"):
                st.write(f"Transactions enregistrées : **{len(ba.transactions)}**")
                if st.button("🗑️ Supprimer ce compte et son historique", key=f"del_ba_{ba.id}"):
                    db.delete(ba); db.commit(); st.rerun()
