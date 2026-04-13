def calculate_compound_interest(principal, monthly_contribution, years, annual_rate):
    """
    Simule la croissance d'un capital via les intérêts composés.
    
    :param principal: Capital initial (ex: 34798 €)
    :param monthly_contribution: Versement mensuel (ex: 600 €)
    :param years: Durée de projection en années
    :param annual_rate: Taux de rendement net estimé (ex: 0.05 pour 5%)
    :return: Une liste de dictionnaires formatée pour générer un graphique pandas/plotly
    """
    timeline = []
    current_value = principal
    total_invested = principal

    # Le point de départ (Année 0)
    timeline.append({
        "Année": 0,
        "Capital Versé": round(total_invested, 2),
        "Valeur Estimée": round(current_value, 2)
    })

    for year in range(1, years + 1):
        # Calcul : Le capital existant prend les intérêts annuels.
        # Les versements réguliers (lissés sur l'année) prennent la moitié du taux annuel (approximation standard).
        current_value = (current_value * (1 + annual_rate)) + (monthly_contribution * 12 * (1 + annual_rate / 2))
        total_invested += (monthly_contribution * 12)
        
        timeline.append({
            "Année": year,
            "Capital Versé": round(total_invested, 2),
            "Valeur Estimée": round(current_value, 2)
        })
        
    return timeline


def convert_currency(amount, exchange_rate):
    """
    Convertit un montant (ex: CHF) vers la devise de référence (EUR).
    Utile pour la vue globale du patrimoine.
    """
    return amount * exchange_rate
