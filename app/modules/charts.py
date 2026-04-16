import streamlit as st
import plotly.express as px
import pandas as pd

# --- GRAPHIQUES PATRIMOINE ---
def render_patrimoine_chart(accounts):
    data = []
    for a in accounts:
        if a.records:
            last = sorted(a.records, key=lambda r: r.date_releve)[-1]
            data.append({"Compte": f"{a.bank_name} ({a.account_type})", "Valeur": last.total_value})
    
    if data:
        df = pd.DataFrame(data)
        # Rendu "Donut" plus moderne
        fig = px.pie(df, values='Valeur', names='Compte', hole=0.6, color_discrete_sequence=["#a855f7", "#6366f1", "#ec4899", "#3b82f6", "#14b8a6"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"), margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

def render_treemap_allocation(accounts):
    """Nouveau graphique très ergonomique pour voir l'allocation détaillée"""
    data = []
    for a in accounts:
        if a.records:
            last = sorted(a.records, key=lambda r: r.date_releve)[-1]
            if last.positions:
                for pos in last.positions:
                    data.append({"Compte": a.bank_name, "Actif": pos.name, "Valeur": pos.total_value})
            else:
                data.append({"Compte": a.bank_name, "Actif": "Fonds Global", "Valeur": last.total_value})
                
    if data:
        df = pd.DataFrame(data)
        fig = px.treemap(df, path=[px.Constant("Mon Patrimoine"), 'Compte', 'Actif'], values='Valeur', color='Compte', color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"))
        st.plotly_chart(fig, use_container_width=True)

def render_account_history(records):
    if not records: return
    df = pd.DataFrame([{"Date": r.date_releve, "Valeur": r.total_value} for r in records]).sort_values("Date")
    fig = px.line(df, x="Date", y="Valeur", markers=True, line_shape="spline")
    fig.update_traces(line_color="#a855f7", marker=dict(size=8, color="#6366f1"))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", yaxis_title="", font=dict(color="#f8fafc"), margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_allocation_chart(euro_val, uc_val):
    if euro_val <= 0 and uc_val <= 0: return
    df = pd.DataFrame([{"Type": "🛡️ Sécurisé (Euros/Livrets)", "Valeur": euro_val}, {"Type": "🚀 Risqué (UC/Actions)", "Valeur": uc_val}])
    fig = px.pie(df, values='Valeur', names='Type', hole=0.5, color_discrete_map={'🛡️ Sécurisé (Euros/Livrets)': '#14b8a6', '🚀 Risqué (UC/Actions)': '#f43f5e'})
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"), margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

# --- GRAPHIQUES BUDGET & CSV ---
def render_budget_pie(transactions):
    expenses = [t for t in transactions if t.amount < 0]
    if not expenses: return
    df = pd.DataFrame([{"Catégorie": t.category, "Montant": abs(t.amount)} for t in expenses])
    df_grouped = df.groupby("Catégorie").sum().reset_index()
    fig = px.pie(df_grouped, values='Montant', names='Catégorie', hole=0.6, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"), margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

def render_expenses_bar_chart(transactions):
    """Nouveau graphique : Classement horizontal des dépenses"""
    expenses = [t for t in transactions if t.amount < 0]
    if not expenses: return
    df = pd.DataFrame([{"Catégorie": t.category, "Montant": abs(t.amount)} for t in expenses])
    df_grouped = df.groupby("Catégorie").sum().reset_index().sort_values(by="Montant", ascending=True)
    
    fig = px.bar(df_grouped, x='Montant', y='Catégorie', orientation='h', color='Montant', color_continuous_scale="Purp")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"), margin=dict(t=0, b=0, l=0, r=0), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

def render_balance_history(transactions):
    valid_tx = [t for t in transactions if t.balance is not None]
    if not valid_tx: return
    df = pd.DataFrame([{"Date": t.date, "Solde": t.balance} for t in valid_tx]).sort_values("Date")
    
    # CORRECTION DU BUG : 'hv' (Horizontal-Vertical) remplace 'step'
    fig = px.line(df, x="Date", y="Solde", line_shape="hv")
    # Ajout d'un remplissage sous la courbe pour un look "App Bancaire" moderne
    fig.update_traces(line_color="#14b8a6", fill='tozeroy', fillcolor="rgba(20, 184, 166, 0.1)")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", yaxis_title="Solde du compte (€)", font=dict(color="#f8fafc"), margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)
