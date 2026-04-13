import json
import time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    # Petit mouchard pour vérifier quelle clé TrueNAS utilise réellement
    key_prefix = api_key[:4]
    
    try:
        client = genai.Client(api_key=api_key)
        
        # 1. Envoi du fichier
        file_upload = client.files.upload(file=pdf_path)
        
        # 2. Pause pour que Google traite le fichier
        time.sleep(8)
        
        prompt = """
        Tu es un expert comptable. Analyse ce document PDF.
        Extrais les informations suivantes au format JSON pur :
        {
            "bank_name": "Nom de la banque",
            "account_type": "PEA ou Assurance-Vie ou Livret",
            "total_value": 1234.56,
            "currency": "EUR",
            "date": "YYYY-MM-DD"
        }
        Ne réponds rien d'autre que le JSON.
        """
        
        # 3. On utilise le modèle par défaut des nouvelles clés AI Studio
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, file_upload]
        )
        
        clean_json = response.text.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        return json.loads(clean_json)
        
    except Exception as e:
        # En cas d'erreur, on affiche le début de la clé pour vérifier !
        return {"error": f"(Clé utilisée: {key_prefix}***) Erreur IA : {str(e)}"}
