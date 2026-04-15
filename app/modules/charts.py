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
        fig = px.pie(df, values='Valeur', names='Compte', hole=0.5, 
                     color_discrete_sequence=["#a855f7", "#6366f1", "#ec4899", "#3b82f6"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"))
        st.plotly_chart(fig, use_container_width=True)

def render_account_history(records):
    df = pd.DataFrame([{"Date": r.date_releve, "Valeur": r.total_value} for r in records])
    df = df.sort_values("Date")
    fig = px.line(df, x="Date", y="Valeur", markers=True, line_shape="spline")
    fig.update_traces(line_color="#a855f7")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"))
    st.plotly_chart(fig, use_container_width=True)
