import streamlit as st
import plotly.express as px
import pandas as pd

def render_patrimoine_chart(accounts):
    """Affiche la répartition du patrimoine par compte (Donut Chart)"""
    data = []
    for a in accounts:
        if a.records:
            # On récupère le dernier relevé en date
            last_record = sorted(a.records, key=lambda r: r.date_releve)[-1]
            data.append({
                "Compte": f"{a.bank_name} ({a.account_type})", 
                "Valeur": last_record.total_value
            })
    
    if data:
        df = pd.DataFrame(data)
        fig = px.pie(
            df, values='Valeur', names='Compte', hole=0.5,
            color_discrete_sequence=["#a855f7", "#6366f1", "#ec4899", "#3b82f6", "#14b8a6"]
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", 
            plot_bgcolor="rgba(0,0,0,0)", 
            font=dict(color="#f8fafc"),
            margin=dict(t=0, b=0, l=0, r=0),
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Aucune donnée de valeur pour le graphique.")

def render_account_history(records):
    """Affiche l'évolution historique d'un compte (Line Chart)"""
    if not records:
        st.caption("Aucun historique disponible.")
        return

    df = pd.DataFrame([
        {"Date": r.date_releve, "Valeur": r.total_value} 
        for r in records
    ])
    df = df.sort_values("Date")
    
    fig = px.line(df, x="Date", y="Valeur", markers=True, line_shape="spline")
    fig.update_traces(line_color="#a855f7", marker=dict(size=8, color="#6366f1"))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        xaxis_title="", yaxis_title="",
        font=dict(color="#f8fafc"),
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)")
    )
    st.plotly_chart(fig, use_container_width=True)

def render_allocation_chart(euro_val, uc_val):
    """Affiche la répartition Sécurité (Euros) vs Risque (UC)"""
    if euro_val <= 0 and uc_val <= 0:
        st.info("💡 Les données d'allocation (UC/Euros) ne sont pas encore disponibles pour ces comptes.")
        return
        
    df = pd.DataFrame([
        {"Type": "🛡️ Fonds Euro (Sécurisé)", "Valeur": euro_val},
        {"Type": "🚀 Unités de Compte (Risque)", "Valeur": uc_val}
    ])
    
    fig = px.pie(
        df, values='Valeur', names='Type', hole=0.5,
        color_discrete_map={
            '🛡️ Fonds Euro (Sécurisé)': '#14b8a6', 
            '🚀 Unités de Compte (Risque)': '#f43f5e'
        }
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        font=dict(color="#f8fafc"),
        margin=dict(t=0, b=0, l=0, r=0)
    )
    st.plotly_chart(fig, use_container_width=True)
