import streamlit as st
import plotly.express as px
from database import SessionLocal, Account

def render_patrimoine_chart(user_id):
    # C'est ici que tu ajoutes facilement tes graphiques
    db = SessionLocal()
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    
    if not accounts:
        st.info("Aucun compte trouvé. Uploade un document.")
        return

    # Exemple de graphique généré facilement
    df = pd.DataFrame([{"Nom": a.account_name, "Valeur": a.total_value} for a in accounts])
    fig = px.pie(df, values='Valeur', names='Nom', hole=0.4, 
                 color_discrete_sequence=px.colors.sequential.Indigo)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
