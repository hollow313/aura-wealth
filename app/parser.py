import json
import time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable."}
    
    try:
        client = genai.Client(api_key=api_key)
        
        # C'est ici ! On utilise 'file=' et non 'path='
        file_upload = client.files.upload(file=pdf_path)
        
        # On attend que le fichier soit digéré
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
        
        models_to_try = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-1.5-pro']
        last_error = ""
        
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, file_upload]
                )
                
                clean_json = response.text.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()
                    
                # Dès qu'on a le JSON, on retourne le résultat (pas de bandeau rouge)
                return json.loads(clean_json)
                
            except Exception as e:
                last_error = str(e)
                continue # On essaye le modèle suivant
                
        # Si on sort de la boucle sans rien, c'est que tous les modèles ont échoué
        return {"error": f"Analyse refusée par l'IA. Détail : {last_error}"}
        
    except Exception as e:
        return {"error": f"Erreur critique de lecture : {str(e)}"}
