import json, time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    try:
        client = genai.Client(api_key=api_key)
        file_upload = client.files.upload(file=pdf_path)
        time.sleep(8) # Temps de digestion Google
        
        prompt = """
        Analyse ce relevé financier et extrais UNIQUEMENT ce JSON :
        {
            "bank_name": "string",
            "account_type": "string",
            "total_value": float,
            "currency": "string",
            "date": "YYYY-MM-DD",
            "dividends": float,
            "fees": float
        }
        Si une donnée est manquante, mets 0.0.
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
