import json
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    try:
        # Initialisation du nouveau client
        client = genai.Client(api_key=api_key)
        
        # Upload sécurisé du PDF
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
        
        # Change gemini-2.0-flash par gemini-1.5-flash
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[prompt, uploaded_file]
        )
        
        # Nettoyage et extraction du JSON
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        return json.loads(raw_text)
        
    except Exception as e:
        return {"error": f"Erreur IA : {str(e)}"}
