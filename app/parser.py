import json, time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    try:
        print(f"\n🚀 [AURA LOG] DÉMARRAGE ANALYSE IA : {pdf_path}")
        client = genai.Client(api_key=api_key)
        
        print("🚀 [AURA LOG] Envoi du fichier à Google...")
        file_upload = client.files.upload(file=pdf_path)
        time.sleep(5) 
        
        prompt = """
        Tu es un expert en gestion de patrimoine. Analyse ce relevé (Assurance Vie, PEA, ou Epargne Salariale PEE/PEG/PER Amundi/Natixis) et extrais ce JSON STRICTEMENT :
        {
            "bank_name": "string (ex: Generali, BoursoBank, Amundi, Natixis)",
            "account_type": "string (ex: Assurance Vie, Epargne Salariale, PEG, PER)",
            "contract_number": "string",
            "date": "YYYY-MM-DD",
            "total_value": float (Valeur totale de l'épargne atteinte),
            "total_invested": float (Total versé depuis l'origine, versements nets ou contributions de l'entreprise. 0.0 si absent),
            "fonds_euro_value": float,
            "uc_value": float,
            "fiscal_date": "YYYY-MM-DD",
            "management_profile": "string",
            "currency": "string (EUR, CHF, USD)",
            "dividends": float (Très important : si c'est Amundi/Natixis, l'Intéressement et la Participation perçus vont ici !),
            "fees": float,
            "positions": [
                {"name": "string (Nom du fonds ou de l'action)", "asset_type": "string", "quantity": float, "unit_price": float, "total_value": float}
            ]
        }
        Règle : S'il y a plusieurs plans sur le même PDF (ex: PEG et PER chez Amundi), fais la somme de tout dans 'total_value' et détaille les fonds dans 'positions'. NE REPONDS QUE LE JSON PUR.
        """
        
        print("🚀 [AURA LOG] Demande de génération à Gemini 2.5 Flash-Lite...")
        response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=[prompt, file_upload])
        
        usage = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        raw_text = response.text.strip()
        start, end = raw_text.find('{'), raw_text.rfind('}') + 1
        
        if start == -1:
            print("❌ [AURA ERROR] Impossible de trouver du JSON dans la réponse.")
            return {"error": "L'IA n'a pas pu structurer la réponse."}
            
        data = json.loads(raw_text[start:end])
        data['tokens'] = usage
        if not data.get('currency'): data['currency'] = "EUR"
        if not data.get('positions'): data['positions'] = []
        
        print("✅ [AURA LOG] Analyse IA terminée et réussie !")
        return data
    except Exception as e:
        print(f"❌ [AURA ERROR] Echec de l'IA : {e}")
        return {"error": str(e)}
