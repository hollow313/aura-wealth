import streamlit as st

def get_user_info():
    headers = st.context.headers
    
    # On cherche PARTOUT (minuscules, majuscules, standard)
    username = headers.get("remote-user") or headers.get("Remote-User") or headers.get("X-Forwarded-User")
    
    if not username:
        return {
            "username": "DevMode",
            "is_member": True, # On force True pour que tu puisses tester le bouton
            "is_admin": True,
            "authenticated": True # On simule l'auth pour débloquer le bouton
        }

    return {
        "username": username,
        "is_member": True, # On simplifie pour l'instant
        "is_admin": True,
        "authenticated": True
    }
