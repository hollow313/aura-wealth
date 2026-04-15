import json, time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    try:
        client = genai.Client(api_key=api_key)
        file_upload = client.files.upload(file=pdf_path)
        time.sleep(10)
        
        prompt = """
        Tu es un analyste financier expert. Analyse ce relevé et extrais UNIQUEMENT ce JSON :
        {
            "bank_name": "string",
            "account_type": "string",
            "contract_number": "string",
            "date": "YYYY-MM-DD",
            "total_value": float,
            "total_invested": float (Chercher 'Total versé depuis l'origine' OU additionner les 'Cumul des primes versées' dans la section fiscale, 0.0 si vraiment introuvable),
            "fonds_euro_value": float,
            "uc_value": float,
            "fiscal_date": "YYYY-MM-DD",
            "management_profile": "string",
            "currency": "string" (Code à 3 lettres ex: EUR, CHF, USD),
            "dividends": float,
            "fees": float,
            "positions": [
                {
                    "name": "string (Nom exact de l'action, de l'ETF ou du fonds)",
                    "asset_type": "string (ETF, Action, Obligation, UC, Fonds Euro)",
                    "quantity": float (Nombre de parts, 0.0 si inconnu),
                    "unit_price": float (Prix unitaire, 0.0 si inconnu),
                    "total_value": float (Valeur totale de cette ligne)
                }
            ]
        }
        Si une valeur est absente, mets 0.0 ou null. Le tableau "positions" doit contenir TOUTES les lignes d'investissement détaillées dans le document. Ne réponds rien d'autre que le JSON pur.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[prompt, file_upload]
        )
        
        usage = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        raw_text = response.text.strip()
        start = raw_text.find('{')
        end = raw_text.rfind('}') + 1
        data = json.loads(raw_text[start:end])
        data['tokens'] = usage
        if not data.get('currency'): data['currency'] = "EUR"
        if not data.get('positions'): data['positions'] = []
            
        return data
    except Exception as e:
        return {"error": str(e)}
