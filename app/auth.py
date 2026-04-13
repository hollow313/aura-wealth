import streamlit as st

def get_user_info():
    headers = st.context.headers
    
    # On cherche l'user dans toutes les variations possibles
    username = headers.get("remote-user") or headers.get("Remote-User")
    
    # On cherche les groupes
    groups_raw = headers.get("remote-groups") or headers.get("Remote-Groups") or ""
    
    # Nettoyage de la liste des groupes
    user_groups = [g.strip().lower() for g in groups_raw.split(",") if g.strip()]

    if not username:
        # Si on ne trouve rien, on est en mode local ou NPM mal configuré
        return {
            "username": "DevMode",
            "is_member": True, 
            "is_admin": True,
            "authenticated": False # En local on ne peut pas sauver le profil
        }

    # LOGIQUE DE VÉRIFICATION
    # On vérifie si 'assurance-vie' est dans la liste envoyée par Authelia
    is_member = "assurance-vie" in user_groups
    is_admin = "admin-assurance-vie" in user_groups

    return {
        "username": username,
        "is_member": is_member,
        "is_admin": is_admin,
        "authenticated": True
    }
