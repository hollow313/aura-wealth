import json
import time
import logging
from google import genai

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
        Tu es un analyste financier. Analyse ce relevé de compte ou d'épargne et extrais les données pour remplir ce JSON STRICTEMENT.

        CONSIGNES :
        1. Va à l'essentiel. Ne cherche pas à interpréter des données complexes.
        2. "total_invested" : Cherche "Total versé depuis l'origine" ou "Cumul des primes versées". Si ce n'est pas clairement indiqué, mets 0.0.
        3. "total_value" : La valeur totale du compte à la date du relevé.
        4. "fonds_euro_value" : Montant sécurisé en euros (Eurossima, Netissima, etc).
        5. "uc_value" : Montant investi sur les marchés (Unités de compte).
        6. "positions" : La liste des actifs détenus (fonds, actions, etc) avec la quantité et la valeur.

        FORMAT JSON REQUIS :
        {
            "bank_name": "string (ex: Generali, Boursorama, Amundi, Natixis)",
            "account_type": "string (ex: Assurance Vie, PEA, Epargne Salariale)",
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
        return {"error": f"Erreur système IA : {str(e)}"}
