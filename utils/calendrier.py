from datetime import date, timedelta

def derniers_jours_ouvres(nb_jours=2, today=None):
    """
    Retourne une plage (date_debut, date_fin)
    correspondant aux N derniers jours ouvrés
    (lundi à samedi, dimanche exclu)
    """
    if today is None:
        today = date.today()

    jours = []
    current = today - timedelta(days=1)

    while len(jours) < nb_jours:
        if current.weekday() != 6:  # 6 = dimanche
            jours.append(current)
        current -= timedelta(days=1)

    return min(jours), max(jours)
