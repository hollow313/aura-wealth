import json, time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    try:
        client = genai.Client(api_key=api_key)
        file_upload = client.files.upload(file=pdf_path)
        time.sleep(10) # Sécurité pour le traitement
        
        prompt = """
        Tu es un analyste financier expert. Analyse ce relevé et extrais ce JSON :
        {
            "bank_name": "string",
            "account_type": "string",
            "contract_number": "string",
            "date": "YYYY-MM-DD",
            "total_value": float,
            "total_invested": float (Total versé depuis l'origine),
            "total_withdrawn": float (Total racheté depuis l'origine),
            "fonds_euro_value": float (Valeur de l'épargne sur le fonds en euros),
            "uc_value": float (Valeur de l'épargne sur les unités de compte),
            "fiscal_date": "YYYY-MM-DD" (Date d'effet fiscale),
            "management_profile": "string" (ex: Mandat Équilibré),
            "currency": "EUR",
            "dividends": float,
            "fees": float
        }
        Si une valeur est absente ou 'N.C.', mets 0.0 ou null.
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
        return data
    except Exception as e:
        return {"error": str(e)}
