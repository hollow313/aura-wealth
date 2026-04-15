def render_allocation_chart(euro_val, uc_val):
    if euro_val == 0 and uc_val == 0:
        st.caption("Données d'allocation manquantes.")
        return
        
    df = pd.DataFrame([
        {"Type": "Fonds Euro (Sécurisé)", "Valeur": euro_val},
        {"Type": "Unités de Compte (Risqué)", "Valeur": uc_val}
    ])
    
    fig = px.pie(df, values='Valeur', names='Type', 
                 color_discrete_map={'Fonds Euro (Sécurisé)': '#14b8a6', 'Unités de Compte (Risqué)': '#f43f5e'},
                 hole=0.5)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#f8fafc"))
    st.plotly_chart(fig, use_container_width=True)
