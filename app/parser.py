import json
import time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    if not api_key:
        return {"error": "Clé API Gemini introuvable dans TrueNAS."}
    
    try:
        # Initialisation du client
        client = genai.Client(api_key=api_key)
        
        # 1. Envoi du PDF
        file_upload = client.files.upload(file=pdf_path)
        
        # 2. On attend que le fichier soit "Ready" côté Google
        # Pour les modèles Lite, 5 à 10 secondes sont idéales.
        time.sleep(8)
        
        prompt = """
        Tu es un analyseur de documents financier. 
        Extrais les données de ce PDF et réponds UNIQUEMENT avec ce JSON :
        {
            "bank_name": "Nom de la banque",
            "account_type": "PEA ou Assurance-Vie ou Livret",
            "total_value": 1234.56,
            "currency": "EUR",
            "date": "YYYY-MM-DD"
        }
        """
        
        # 3. APPEL AU MODÈLE GEMINI 2.5 FLASH-LITE
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[prompt, file_upload]
        )
        
        if not response.text:
            return {"error": "L'IA a répondu mais le texte est vide."}

        # Nettoyage pour ne garder que le JSON
        raw_text = response.text.strip()
        start = raw_text.find('{')
        end = raw_text.rfind('}') + 1
        
        if start == -1 or end == 0:
            return {"error": "Format JSON non détecté dans la réponse de l'IA."}
            
        return json.loads(raw_text[start:end])
        
    except Exception as e:
        # On affiche l'erreur brute pour comprendre si c'est encore un problème de quota
        return {"error": f"Erreur avec Gemini 2.5 : {str(e)}"}
