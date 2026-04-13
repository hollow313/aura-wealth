import json
import time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    try:
        client = genai.Client(api_key=api_key)
        
        # 1. Upload du fichier
        file_upload = client.files.upload(path=pdf_path)
        
        # 2. Attendre que Google traite le fichier (Indispensable pour les gros PDF)
        # On attend quelques secondes pour éviter le 404/Not Found
        time.sleep(3) 
        
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
        
        # 3. Appel au modèle le plus stable (on reste sur Flash 1.5 qui est le plus robuste en Free Tier)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[prompt, file_upload]
        )
        
        if not response.text:
            return {"error": "L'IA a renvoyé une réponse vide."}

        # Nettoyage du texte pour extraire le JSON
        clean_json = response.text.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        return json.loads(clean_json)
        
    except Exception as e:
        # On simplifie l'erreur pour ne plus avoir de confusion
        return {"error": f"Analyse interrompue : {str(e)}"}
