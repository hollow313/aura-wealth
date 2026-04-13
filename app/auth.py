import streamlit as st

def get_user_info():
    headers = st.context.headers

    # Streamlit convertit les headers HTTP en minuscules !
    username = headers.get("remote-user", headers.get("Remote-User"))
    email = headers.get("remote-email", headers.get("Remote-Email", "Non renseigné"))
    groups_str = headers.get("remote-groups", headers.get("Remote-Groups", ""))
    
    user_groups = [g.strip() for g in groups_str.split(",") if g.strip()]

    # Mode développement (sécurité si le proxy ne passe rien)
    if not username:
        return {
            "username": "DevMode",
            "email": "dev@aura.local",
            "is_member": True,
            "is_admin": True,
            "authenticated": False 
        }

    return {
        "username": username,
        "email": email,
        "is_member": "assurance-vie" in user_groups,
        "is_admin": "admin-assurance-vie" in user_groups,
        "authenticated": True
    }
