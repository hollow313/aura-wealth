import json
import time
import logging
from google import genai

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def check_quota_and_parse(pdf_path, api_key):
    try:
        # On évite d'afficher le chemin complet au cas où il resterait des caractères spéciaux
        logger.info("🚀 [AURA] Démarrage de l'analyse IA du document...")
        client = genai.Client(api_key=api_key)
        
        logger.info("🚀 [AURA] Upload du document vers Gemini...")
        file_upload = client.files.upload(file=pdf_path)
        
        logger.info("🚀 [AURA] Document uploadé. Pause de 5 secondes...")
        time.sleep(5) 
        
        prompt = """
        Tu es un auditeur financier expert. Analyse ce relevé (Assurance Vie Generali/Bourso, PEA, ou Epargne Salariale PEE/PEG/PER Amundi/Natixis) et extrais ce JSON STRICTEMENT.

        RÈGLES D'EXTRACTION FINANCIÈRE (TRÈS IMPORTANT) :
        1. "total_invested" (Capital Versé) : Cherche "Total versé depuis l'origine". SI ABSENT (notamment sur les relevés 2020/2021), va dans la section 'Fiscalité' ou 'Informations Fiscales' et prends le montant du "Cumul des primes versées". Si Epargne salariale, prends les versements nets/contributions.
        2. "dividends" : Si c'est de l'épargne salariale (Amundi/Natixis), additionne l'"Intéressement", la "Participation" et l'"Abondement" de l'année.
        3. "fonds_euro_value" : Somme des fonds sécurisés (Eurossima, Netissima, Fonds en euros).
        4. "uc_value" : Somme des Unités de Compte, actions, ETF.
        5. "positions" : Liste CHAQUE actif présent avec sa quantité et son prix unitaire.
        6. S'il y a un PEG et un PER sur le même document, fusionne le tout dans total_value.

        FORMAT JSON REQUIS :
        {
            "bank_name": "string (ex: Generali, BoursoBank, Amundi, Natixis)",
            "account_type": "string (ex: Assurance Vie, Epargne Salariale, PEG, PER)",
            "contract_number": "string",
            "date": "YYYY-MM-DD",
            "total_value": float,
            "total_invested": float,
            "fonds_euro_value": float,
            "uc_value": float,
            "fiscal_date": "YYYY-MM-DD",
            "management_profile": "string",
            "currency": "string (EUR, CHF, USD)",
            "dividends": float,
            "fees": float,
            "positions": [
                {"name": "string", "asset_type": "string", "quantity": float, "unit_price": float, "total_value": float}
            ]
        }
        Règle d'or : TOUTES les valeurs numériques doivent être des Float (ex: 400.0). Ne renvoie jamais de texte ou null pour un chiffre. NE REPONDS QUE LE JSON PUR.
        """
        
        logger.info("🚀 [AURA] Appel à Gemini 2.5 Flash-Lite...")
        response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=[prompt, file_upload])
        
        logger.info("🚀 [AURA] Réponse reçue. Traitement du JSON...")
        usage = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        raw_text = response.text.strip()
        
        # Nettoyage robuste du Markdown
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1]
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            
        if "```" in raw_text:
            raw_text = raw_text.split("```")[0]
            
        raw_text = raw_text.strip()
        
        start = raw_text.find('{')
        end = raw_text.rfind('}') + 1
        
        if start == -1:
            logger.error("❌ [AURA ERROR] JSON introuvable dans la réponse de l'IA.")
            return {"error": "L'IA n'a pas pu structurer la réponse."}
            
        data = json.loads(raw_text[start:end])
        data['tokens'] = usage
        if not data.get('currency'): 
            data['currency'] = "EUR"
        if not data.get('positions'): 
            data['positions'] = []
        
        logger.info("✅ [AURA] Analyse IA terminée avec succès !")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ [AURA CRASH] Erreur de formatage JSON. Texte brut: {raw_text}")
        return {"error": "L'IA a renvoyé des données mal formatées. Réessayez."}
    except Exception as e:
        logger.error(f"❌ [AURA CRASH] Erreur critique : {str(e)}")
        return {"error": f"Erreur IA : {str(e)}"}
