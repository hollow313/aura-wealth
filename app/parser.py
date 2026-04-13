import json
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    try:
        # On utilise le nouveau client officiel de Google
        client = genai.Client(api_key=api_key)
        
        # Envoi sécurisé du PDF aux serveurs de Google
        uploaded_file = client.files.upload(file=pdf_path)
        
        prompt = """
        Analyse ce relevé de compte bancaire.
        Renvoie UNIQUEMENT un objet JSON pur avec ces clés exactes :
        - bank_name (Nom de la banque)
        - account_type (Type de compte : PEA, Assurance-Vie, Livret A, etc.)
        - total_value (Nombre, la valeur totale du compte)
        - currency (Devise : EUR, CHF, USD...)
        - date (Format YYYY-MM-DD)
        """
        
        # --- SYSTÈME ANTI-PLANTAGE (FALLBACK) ---
        # On tente plusieurs modèles au cas où l'un d'eux soit bloqué ou saturé
        models_to_try = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-1.5-pro']
        response = None
        last_error = ""
        
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, uploaded_file]
                )
                break # Si l'analyse réussit, on sort de la boucle !
            except Exception as e:
                last_error = str(e)
                continue # Si ça échoue, on passe au modèle suivant
        
        if not response:
            return {"error": f"Google a refusé l'analyse sur tous les modèles. Détail : {last_error}"}

        # Nettoyage et extraction du JSON renvoyé par l'IA
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        return json.loads(raw_text)
        
    except Exception as e:
        return {"error": f"Erreur critique IA : {str(e)}"}
