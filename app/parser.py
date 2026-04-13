import google.generativeai as genai
import json
from datetime import datetime
from database import SessionLocal, GlobalSettings, TokenUsage

def check_quota_and_parse(pdf_path, api_key):
    db = SessionLocal()
    settings = db.query(GlobalSettings).first()
    usage_today = db.query(TokenUsage).filter_by(date=datetime.now().date()).first()
    
    if not usage_today:
        usage_today = TokenUsage(date=datetime.now().date(), tokens_used=0)
        db.add(usage_today)

    # CALCUL DE LA LIMITE À 70%
    max_allowed = int(settings.max_daily_tokens * 0.70)

    if usage_today.tokens_used >= max_allowed:
        db.close()
        return {"error": f"Quota de sécurité atteint ({max_allowed} tokens). Réessaie demain ou augmente la limite admin."}

    # PROMPT UNIVERSEL
    prompt = """
    Tu es un expert financier. Analyse ce document (relevé bancaire, PEA, Assurance Vie, CTO, etc.).
    Peu importe la banque (Bourso, Crédit Mutuel, UBS) ou la langue.
    Extrais les informations suivantes sous forme de JSON strict :
    {
      "bank_name": "Nom de l'établissement",
      "account_type": "Type (PEA, Assurance Vie, etc.)",
      "currency": "EUR ou CHF",
      "total_value": nombre décimal de la valeur totale atteinte,
      "date": "YYYY-MM-DD du relevé",
      "assets": [
        {"name": "Nom du fonds/action", "type": "Actions/Obligations/Fonds Euro/Cash", "amount": nombre décimal}
      ]
    }
    Réponds UNIQUEMENT le JSON.
    """

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Upload et exécution
    file = genai.upload_file(path=pdf_path)
    response = model.generate_content([prompt, file])
    
    # Mise à jour des tokens
    # Gemini renvoie l'usage dans response.usage_metadata.total_token_count
    tokens_consumed = response.usage_metadata.total_token_count if response.usage_metadata else 5000 # Fallback
    usage_today.tokens_used += tokens_consumed
    db.commit()
    db.close()

    # Nettoyage de la réponse pour obtenir le JSON
    text_response = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(text_response)
