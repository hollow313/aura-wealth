import streamlit as st
import plotly.express as px
import pandas as pd

def render_patrimoine_chart(accounts):
    data = []
    for a in accounts:
        if a.records:
            last = sorted(a.records, key=lambda r: r.date_releve)[-1]
            data.append({"Compte": f"{a.bank_name} ({a.account_type})", "Valeur": last.total_value})
    
    if data:
        df = pd.DataFrame(data)
        fig = px.pie(df, values='Valeur', names='Compte', hole=0.5, color_discrete_sequence=["#a855f7", "#6366f1", "#ec4899", "#3b82f6", "#14b8a6"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"), margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig)

def render_account_history(records):
    if not records: return
    df = pd.DataFrame([{"Date": r.date_releve, "Valeur": r.total_value} for r in records]).sort_values("Date")
    fig = px.line(df, x="Date", y="Valeur", markers=True, line_shape="spline")
    fig.update_traces(line_color="#a855f7", marker=dict(size=8, color="#6366f1"))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", yaxis_title="", font=dict(color="#f8fafc"), margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig)

def render_allocation_chart(euro_val, uc_val):
    if euro_val <= 0 and uc_val <= 0: return
    df = pd.DataFrame([{"Type": "🛡️ Sécurisé (Euros/Livrets)", "Valeur": euro_val}, {"Type": "🚀 Risqué (UC/Actions)", "Valeur": uc_val}])
    fig = px.pie(df, values='Valeur', names='Type', hole=0.5, color_discrete_map={'🛡️ Sécurisé (Euros/Livrets)': '#14b8a6', '🚀 Risqué (UC/Actions)': '#f43f5e'})
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"), margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig)
