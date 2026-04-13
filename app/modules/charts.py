import streamlit as st
import plotly.express as px
import pandas as pd
from database import SessionLocal, Account, Record

def render_patrimoine_chart(user_id):
    """Génère le graphique en anneau (Donut) du patrimoine global"""
    db = SessionLocal()
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    
    if not accounts:
        st.info("Aucun compte trouvé. Ajoutez un premier document pour commencer.")
        db.close()
        return

    data = []
    for a in accounts:
        last_record = db.query(Record).filter(Record.account_id == a.id).order_by(Record.date_releve.desc()).first()
        val = last_record.total_value if last_record else 0
        if val > 0:
            data.append({"Nom": f"{a.bank_name} ({a.account_type})", "Valeur": val})

    df = pd.DataFrame(data)
    
    if not df.empty:
        # Couleurs Néon personnalisées !
        neon_colors = ["#a855f7", "#6366f1", "#ec4899", "#3b82f6", "#14b8a6", "#f59e0b"]
        fig = px.pie(df, values='Valeur', names='Nom', hole=0.5, 
                     color_discrete_sequence=neon_colors)
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", 
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f8fafc"),
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Les comptes sont à zéro.")
        
    db.close()

def render_account_history(account_id):
    """Génère la courbe d'évolution temporelle pour un compte spécifique"""
    db = SessionLocal()
    records = db.query(Record).filter(Record.account_id == account_id).order_by(Record.date_releve).all()
    
    if not records:
        st.info("Aucun historique pour ce compte.")
        db.close()
        return
        
    df = pd.DataFrame([{"Date": r.date_releve, "Valeur": r.total_value} for r in records])
    
    fig = px.line(df, x="Date", y="Valeur", markers=True, line_shape="spline")
    
    fig.update_traces(line_color="#a855f7", marker=dict(size=8, color="#6366f1"))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="",
        yaxis_title="",
        font=dict(color="#f8fafc"),
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)")
    )
    
    st.plotly_chart(fig, use_container_width=True)
    db.close()
