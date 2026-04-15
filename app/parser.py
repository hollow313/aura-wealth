import json, time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    try:
        client = genai.Client(api_key=api_key)
        
        # Upload du fichier chez Google
        file_upload = client.files.upload(file=pdf_path)
        
        # Pause de sécurité pour laisser le temps aux serveurs Google d'analyser le PDF
        time.sleep(10)
        
        # Le "Cerveau" : Prompt ultra-détaillé
        prompt = """
        Tu es un analyste financier expert. Analyse ce relevé bancaire ou d'assurance-vie et extrais UNIQUEMENT ce JSON :
        {
            "bank_name": "string (Nom de l'établissement, ex: Boursorama, Generali)",
            "account_type": "string (ex: Assurance-Vie, PEA, Compte Titres)",
            "contract_number": "string (Le numéro de contrat ou de compte)",
            "date": "YYYY-MM-DD (La date d'arrêté du relevé, très important)",
            "total_value": float (La valeur totale du portefeuille ou l'épargne atteinte),
            "total_invested": float (TRÈS IMPORTANT : Cherche 'Total versé depuis l'origine'. Si absent sur la première page, fouille dans les pages annexes ou fiscales et cherche 'Cumul des primes versées' ou 'Total des versements'. Si tu ne trouves absolument rien de global, mets 0.0),
            "fonds_euro_value": float (Montant total sécurisé sur le fonds en euros, 0.0 si absent),
            "uc_value": float (Montant total risqué sur les unités de compte, 0.0 si absent),
            "fiscal_date": "YYYY-MM-DD (Date d'effet fiscale ou d'ouverture)",
            "management_profile": "string (ex: Gestion libre, Mandat équilibré)",
            "currency": "string (Code à 3 lettres ex: EUR, CHF, USD. Si symbole €, mets EUR)",
            "dividends": float (Total des dividendes ou coupons perçus sur la période),
            "fees": float (Total des frais prélevés sur la période),
            "positions": [
                {
                    "name": "string (Nom exact de l'action, de l'ETF, de la SICAV ou du fonds euro)",
                    "asset_type": "string (ETF, Action, Obligation, UC, Fonds Euro)",
                    "quantity": float (Nombre de parts, 0.0 si non applicable),
                    "unit_price": float (Prix unitaire ou valeur de la part, 0.0 si non applicable),
                    "total_value": float (Valeur totale de cette ligne précise)
                }
            ]
        }
        RÈGLES STRICTES :
        1. Si une valeur est absente, mets 0.0 ou null. 
        2. Le tableau "positions" doit contenir TOUTES les lignes d'investissement détaillées dans le document (chaque action, chaque fonds).
        3. Ne réponds absolument rien d'autre que le JSON pur, sans texte avant ni après, et sans bloc markdown.
        """
        
        # Appel au modèle
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[prompt, file_upload]
        )
        
        # Récupération de la consommation de tokens
        usage = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        
        # Nettoyage de la réponse pour extraire le JSON
        raw_text = response.text.strip()
        start = raw_text.find('{')
        end = raw_text.rfind('}') + 1
        data = json.loads(raw_text[start:end])
        
        # Injection des tokens dans le résultat
        data['tokens'] = usage
        
        # Sécurisations post-extraction
        if not data.get('currency'): 
            data['currency'] = "EUR"
        if not data.get('positions'): 
            data['positions'] = []
            
        return data

    except Exception as e:
        return {"error": str(e)}
