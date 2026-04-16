import pandas as pd
import requests
from datetime import datetime

def safe_float(value):
    """Convertit proprement les montants français en float (gère les espaces et les points des milliers)"""
    try:
        if pd.isna(value) or value is None or value == "": return 0.0
        if isinstance(value, str):
            # 1. On retire les espaces insécables ou normaux (séparateurs de milliers français)
            value = value.replace('\xa0', '').replace(' ', '').replace('€', '')
            # 2. Si on a un point ET une virgule (ex: 1.200,50), le point est un séparateur de milliers
            if '.' in value and ',' in value:
                value = value.replace('.', '') # On supprime le point des milliers
                value = value.replace(',', '.') # On transforme la virgule décimale en point
            # 3. S'il n'y a qu'une virgule (ex: 1200,50), on la remplace par un point
            elif ',' in value:
                value = value.replace(',', '.')
        return float(value)
    except: return 0.0

def manage_token_resets(profile, db):
    today = datetime.now().date()
    current_week = today.isocalendar()[1]
    updated = False
    if profile.last_daily_reset != today:
        profile.token_used_daily = 0
        profile.last_daily_reset = today
        updated = True
    if profile.last_weekly_reset != current_week:
        profile.token_used_weekly = 0
        profile.last_weekly_reset = current_week
        updated = True
    if updated: db.commit()

# --- GESTION DES DEVISES ---
_rates_cache = None
_rates_time = None

def get_exchange_rates():
    global _rates_cache, _rates_time
    now = datetime.now().timestamp()
    if _rates_cache is None or _rates_time is None or (now - _rates_time > 3600):
        try: 
            _rates_cache = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=3).json().get("rates", {"EUR": 1.0, "CHF": 0.98, "USD": 1.08})
        except: 
            _rates_cache = {"EUR": 1.0, "CHF": 0.98, "USD": 1.08}
        _rates_time = now
    return _rates_cache

def convert_to_eur(amount, currency):
    if currency == "EUR" or not currency: return amount
    rates = get_exchange_rates()
    rate = rates.get(currency.upper(), 1.0)
    return amount / rate if rate > 0 else amount

def get_multi_currency_caption(amount_eur, active_currencies):
    currs = [c.strip() for c in active_currencies.split(",") if c.strip() and c.strip() != "EUR"]
    if not currs: return ""
    rates = get_exchange_rates()
    res = []
    for c in currs:
        rate = rates.get(c, 1.0)
        res.append(f"≈ {amount_eur * rate:,.0f} {c}")
    return " | ".join(res)

# --- AUTO-CATEGORISATION (BUDGET) ---
def categorize_transaction(label, amount):
    lbl = str(label).upper()
    if amount > 0:
        if any(k in lbl for k in ["SALA", "PAIE", "REMUNERATION"]): return "Salaire"
        if any(k in lbl for k in ["WILLIS", "CPAM", "MUTUELLE", "REMB", "SECU"]): return "Remboursement Santé"
        if any(k in lbl for k in ["CAF", "IMPOT", "TRESOR"]): return "Aides & Impôts"
        if any(k in lbl for k in ["VIR", "VIREMENT"]): return "Virement Entrant"
        return "Revenus (Autre)"
    else:
        if any(k in lbl for k in ["AMAZON", "PAYPAL", "CDISCOUNT", "FNAC", "ALIEXPRESS"]): return "Achats & E-commerce"
        if any(k in lbl for k in ["AUCHAN", "CARREFOUR", "LECLERC", "INTERMARCHE", "LIDL", "ALDI", "MONOPRIX", "U EXPR", "SUPER U"]): return "Alimentation & Supermarché"
        if any(k in lbl for k in ["ASSURANCE", "ALLIANZ", "AXA", "MACIF", "MAAF", "MATMUT", "DIRECT ASS", "PACIFICA"]): return "Assurances"
        if any(k in lbl for k in ["TOTAL", "ESSO", "SHELL", "STATION", "PEAGE", "SNCF", "UBER", "VINCI"]): return "Transport & Auto"
        if any(k in lbl for k in ["EDF", "ENGIE", "ENI", "EAU", "VEOLIA", "SUEZ"]): return "Logement & Énergies"
        if any(k in lbl for k in ["ORANGE", "FREE", "BOUYGUES", "SFR", "NETFLIX", "SPOTIFY", "APPLE"]): return "Abonnements & Télécom"
        if any(k in lbl for k in ["PHARMACIE", "MEDECIN", "HOPITAL", "CLINIQUE", "LABO", "DOCTOLIB"]): return "Santé"
        if any(k in lbl for k in ["RESTAURANT", "UBER EATS", "DELIVEROO", "MCDO", "KFC", "BURGER KING", "BAKERY", "BOULANGERIE", "CREPERIE"]): return "Restaurants & Sorties"
        if any(k in lbl for k in ["RETRAIT", "DAB", "DISTRIBUTEUR"]): return "Retraits Espèces"
        return "Dépenses (Autre)"
