import streamlit as st
import os
from database import SessionLocal, GlobalSettings, TokenUsage
from datetime import datetime

def admin_page(current_user):
    st.title("🛡️ Centre de Commandement")
    st.markdown("Gérez les quotas d'intelligence artificielle et l'espace de stockage d'Aura Wealth.")

    db = SessionLocal()
    
    # Initialisation des paramètres globaux s'ils n'existent pas
    settings = db.query(GlobalSettings).first()
    if not settings:
        settings = GlobalSettings(max_daily_tokens=100000)
        db.add(settings)
        db.commit()

    # Récupération de la consommation du jour
    usage_today = db.query(TokenUsage).filter_by(date=datetime.now().date()).first()
    tokens_used = usage_today.tokens_used if usage_today else 0
    
    # --- SECTION IA & QUOTAS ---
    st.subheader("🤖 Intelligence Artificielle (Gemini)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tokens Consommés (Aujourd'hui)", f"{tokens_used:,}")
    with col2:
        st.metric("Limite Maximale", f"{settings.max_daily_tokens:,}")
    with col3:
        # Calcul du seuil de coupure strict à 70%
        threshold = int(settings.max_daily_tokens * 0.70)
        st.metric("Seuil de Coupure (70%)", f"{threshold:,}")

    # Barre de progression visuelle
    progress = min(tokens_used / threshold, 1.0) if threshold > 0 else 0.0
    st.progress(progress, text="Consommation par rapport au seuil de sécurité")
    
    if progress >= 1.0:
        st.error("⚠️ Le quota de sécurité est atteint. Le traitement de nouveaux PDF est bloqué jusqu'à demain.")

    with st.expander("⚙️ Modifier la limite journalière"):
        new_limit = st.number_input("Nouvelle limite (Tokens)", min_value=10000, value=settings.max_daily_tokens, step=10000)
        if st.button("Enregistrer la configuration"):
            settings.max_daily_tokens = new_limit
            db.commit()
            st.success("Paramètres mis à jour avec succès.")
            st.rerun()

    st.divider()

    # --- SECTION GESTION DES FICHIERS ---
    st.subheader("📁 Gestion du Stockage (TrueNAS)")
    storage_path = "/app/storage"
    
    # S'assure que le dossier existe (utile au premier lancement)
    os.makedirs(storage_path, exist_ok=True)
    
    all_files = []
    total_size = 0
    
    # Parcours des dossiers utilisateurs/comptes
    for root, dirs, files in os.walk(storage_path):
        for file in files:
            filepath = os.path.join(root, file)
            size = os.path.getsize(filepath)
            total_size += size
            # Affichage propre (sans le chemin absolu /app/storage/)
            all_files.append({
                "Chemin relatif": filepath.replace(f"{storage_path}/", ""), 
                "Taille (KB)": round(size / 1024, 2)
            })

    st.markdown(f"**Espace total occupé sur le volume :** `{total_size / (1024*1024):.2f} MB`")
    
    if all_files:
        st.dataframe(all_files, use_container_width=True)
        
        # Outil de suppression manuelle
        file_to_delete = st.selectbox("Sélectionnez un fichier à supprimer définitivement du serveur", [f["Chemin relatif"] for f in all_files])
        if st.button("🗑️ Purger le fichier", type="primary"):
            try:
                os.remove(os.path.join(storage_path, file_to_delete))
                st.success(f"Le fichier {file_to_delete} a été supprimé.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur de suppression : {e}")
    else:
        st.info("Aucun document PDF n'est actuellement stocké sur le serveur.")

    db.close()
