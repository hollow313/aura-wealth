import json
import time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    try:
        client = genai.Client(api_key=api_key)
        
        # 1. Envoi du fichier à Google
        file_upload = client.files.upload(file=pdf_path)
        
        # 2. PAUSE STRATÉGIQUE (10 secondes)
        # Google a besoin de temps pour traiter le PDF de son côté.
        time.sleep(10)
        
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
        
        # 3. Appel direct au modèle stable (plus de boucle qui masque l'erreur)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[prompt, file_upload]
        )
        
        # 4. Nettoyage et extraction du JSON
        clean_json = response.text.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        return json.loads(clean_json)
        
    except Exception as e:
        # S'il y a une erreur, on verra ENFIN la vraie !
        return {"error": f"Erreur d'analyse : {str(e)}"}
