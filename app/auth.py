import streamlit as st

def get_user_info():
    """
    Récupère les informations de l'utilisateur injectées par Authelia/NPM 
    via les headers HTTP.
    """
    # Récupération des headers via le contexte Streamlit
    headers = st.context.headers

    # Extraction des informations (noms des headers standards Authelia)
    # Note : NPM doit être configuré pour transmettre ces headers
    username = headers.get("Remote-User", None)
    email = headers.get("Remote-Email", "Non renseigné")
    groups_str = headers.get("Remote-Groups", "") # Liste séparée par des virgules
    
    # Transformation de la chaîne de groupes en liste pour faciliter la recherche
    user_groups = [g.strip() for g in groups_str.split(",") if g.strip()]

    # --- LOGIQUE DE SÉCURITÉ AURA ---
    # 1. Accès de base : doit être dans le groupe 'assurance-vie'
    is_member = "assurance-vie" in user_groups
    
    # 2. Accès Admin : doit être dans le groupe 'admin-assurance-vie'
    is_admin = "admin-assurance-vie" in user_groups

    # Mode développement : si tu lances l'app en local sans proxy, 
    # on peut simuler un utilisateur si besoin (à retirer en prod)
    if not username:
        # En local (dev), on peut retourner un utilisateur fictif pour tester l'UI
        return {
            "username": "DevMode",
            "email": "dev@aura.local",
            "is_member": True,
            "is_admin": True,
            "authenticated": False # Indique que ce n'est pas une vraie auth
        }

    return {
        "username": username,
        "email": email,
        "is_member": is_member,
        "is_admin": is_admin,
        "authenticated": True
    }
