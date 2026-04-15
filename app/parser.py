import json, time
from google import genai

def check_quota_and_parse(pdf_path, api_key):
    try:
        print(f"\n🚀 [AURA LOG] DÉMARRAGE DE L'ANALYSE IA : {pdf_path}")
        client = genai.Client(api_key=api_key)
        
        print("🚀 [AURA LOG] Étape 1/4 : Upload du PDF vers Gemini...")
        file_upload = client.files.upload(file=pdf_path)
        
        print("🚀 [AURA LOG] Étape 2/4 : Repos de 5 secondes pour sécuriser l'API...")
        time.sleep(5) 
        
        prompt = """
        Tu es un expert en gestion de patrimoine. Analyse ce relevé financier (Assurance Vie, PEA, ou Epargne Salariale PEE/PEG/PER) et extrais ce JSON STRICTEMENT :
        {
            "bank_name": "string (ex: Generali, BoursoBank, Amundi, Natixis)",
            "account_type": "string (ex: Assurance Vie, Epargne Salariale, PEG, PER)",
            "contract_number": "string (ex: N° de compte ou d'adhésion)",
            "date": "YYYY-MM-DD (Date du relevé ou de l'épargne atteinte)",
            "total_value": float (Valeur totale ou épargne atteinte),
            "total_invested": float (Capital versé, cumul des primes, ou versements nets. S'il y a de l'intéressement/participation, inclus-le ici. 0.0 si introuvable),
            "fonds_euro_value": float (Valeur sur fonds sécurisé en euros),
            "uc_value": float (Valeur sur les marchés/actions/unités de compte),
            "fiscal_date": "YYYY-MM-DD",
            "management_profile": "string (ex: Mandat Equilibré, Gestion libre)",
            "currency": "string (EUR, CHF, USD)",
            "dividends": float (Intéressement, participation ou dividendes perçus sur l'année),
            "fees": float,
            "positions": [
                {
                    "name": "string (Nom du fonds, de l'ETF ou de l'action)",
                    "asset_type": "string",
                    "quantity": float,
                    "unit_price": float,
                    "total_value": float
                }
            ]
        }
        Règle stricte : S'il y a plusieurs plans (ex: PEG et PER chez Amundi), fais la somme de tout dans 'total_value' et détaille les fonds dans 'positions'.
        Si une valeur est absente, mets 0.0 ou null. NE REPONDS QUE LE JSON.
        """
        
        print("🚀 [AURA LOG] Étape 3/4 : Génération du contenu (Attente de la réponse de l'IA)...")
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[prompt, file_upload]
        )
        
        print("🚀 [AURA LOG] Étape 4/4 : Réponse reçue ! Formatage du JSON...")
        if not response.text:
            print("❌ [AURA ERROR] Réponse vide de Gemini.")
            return {"error": "L'IA n'a renvoyé aucune donnée (blocage de sécurité potentiel)."}

        usage = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        raw_text = response.text.strip()
        
        start = raw_text.find('{')
        end = raw_text.rfind('}') + 1
        
        if start == -1 or end == 0:
            print(f"❌ [AURA ERROR] JSON introuvable dans la réponse : {raw_text[:100]}...")
            return {"error": "Impossible d'extraire les données financières du document."}
            
        data = json.loads(raw_text[start:end])
        data['tokens'] = usage
        if not data.get('currency'): data['currency'] = "EUR"
        if not data.get('positions'): data['positions'] = []
        
        print("✅ [AURA LOG] Extraction terminée avec succès !")
        return data
        
    except Exception as e:
        print(f"❌ [AURA CRITICAL ERROR] Le script a planté : {e}")
        return {"error": f"Erreur critique lors de l'analyse : {str(e)}"}
