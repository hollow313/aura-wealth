import json, time, logging
from google import genai

# Configuration pour forcer l'affichage dans la console Docker/TrueNAS
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def check_quota_and_parse(pdf_path, api_key):
    try:
        logger.info(f"🚀 [AURA] Démarrage de l'analyse IA : {pdf_path}")
        client = genai.Client(api_key=api_key)
        
        logger.info("🚀 [AURA] Upload du document vers Gemini...")
        file_upload = client.files.upload(file=pdf_path)
        
        logger.info("🚀 [AURA] Document uploadé. Pause de 5 secondes...")
        time.sleep(5) 
        
        prompt = """
        Tu es un expert en gestion de patrimoine. Analyse ce relevé (Assurance Vie, PEA, ou Epargne Salariale PEE/PEG/PER Amundi/Natixis) et extrais ce JSON STRICTEMENT :
        {
            "bank_name": "string (ex: Generali, BoursoBank, Amundi, Natixis)",
            "account_type": "string (ex: Assurance Vie, Epargne Salariale, PEG, PER)",
            "contract_number": "string",
            "date": "YYYY-MM-DD",
            "total_value": float (Valeur totale de l'épargne atteinte),
            "total_invested": float (Total versé depuis l'origine, versements nets. S'il y a de l'intéressement/participation, inclus-le ici. 0.0 si absent),
            "fonds_euro_value": float,
            "uc_value": float,
            "fiscal_date": "YYYY-MM-DD",
            "management_profile": "string",
            "currency": "string (EUR, CHF, USD)",
            "dividends": float (Intéressement et Participation perçus vont ici !),
            "fees": float,
            "positions": [
                {"name": "string (Nom du fonds ou de l'action)", "asset_type": "string", "quantity": float, "unit_price": float, "total_value": float}
            ]
        }
        Règle : S'il y a plusieurs plans sur le même PDF (ex: PEG et PER), fais la somme dans 'total_value' et détaille les fonds dans 'positions'. NE REPONDS QUE LE JSON PUR.
        """
        
        logger.info("🚀 [AURA] Appel à Gemini 2.5 Flash-Lite...")
        response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=[prompt, file_upload])
        
        logger.info("🚀 [AURA] Réponse reçue. Traitement du JSON...")
        usage = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        raw_text = response.text.strip()
        start, end = raw_text.find('{'), raw_text.rfind('}') + 1
        
        if start == -1:
            logger.error("❌ [AURA ERROR] Impossible de trouver du JSON dans la réponse.")
            return {"error": "L'IA n'a pas pu structurer la réponse."}
            
        data = json.loads(raw_text[start:end])
        data['tokens'] = usage
        if not data.get('currency'): data['currency'] = "EUR"
        if not data.get('positions'): data['positions'] = []
        
        logger.info("✅ [AURA] Analyse IA terminée avec succès !")
        return data
        
    except Exception as e:
        logger.error(f"❌ [AURA CRASH] Erreur critique : {str(e)}")
        return {"error": f"Erreur IA : {str(e)}"}
