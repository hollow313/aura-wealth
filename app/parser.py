import json
import time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    key_prefix = api_key[:4]
    
    try:
        # On garde le nouveau client
        client = genai.Client(api_key=api_key)
        
        # 1. Envoi du fichier
        file_upload = client.files.upload(file=pdf_path)
        
        # 2. On laisse 10 secondes (mieux vaut trop que pas assez)
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
        
        # 3. ON FORCE LE MODÈLE 1.5-FLASH (Le plus généreux en quota gratuit)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[prompt, file_upload]
        )
        
        if not response or not response.text:
             return {"error": "L'IA n'a pas pu générer de texte."}

        # Nettoyage ultra-précis du JSON
        raw_text = response.text.strip()
        # On cherche le début { et la fin } au cas où l'IA ajoute du texte autour
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            return {"error": f"L'IA n'a pas renvoyé de JSON valide : {raw_text[:100]}"}
            
        json_str = raw_text[start_idx:end_idx]
        return json.loads(json_str)
        
    except Exception as e:
        return {"error": f"(Clé: {key_prefix}) Erreur d'analyse : {str(e)}"}
