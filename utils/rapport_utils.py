from datetime import timedelta

JOURS_FR = {
    0: "Lundi",
    1: "Mardi",
    2: "Mercredi",
    3: "Jeudi",
    4: "Vendredi",
    5: "Samedi",
    6: "Dimanche",
}

MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}

def format_date_fr(d):
    return f"{JOURS_FR[d.weekday()]} {d.day} {MOIS_FR[d.month]} {d.year}"


def jours_non_travailles_individuels(date_debut, date_fin, jours_vendus_agent):
    """
    Calcule les jours ouvrés (lundi–samedi) sans activité
    pour UN agent donné
    """
    jours_absents = []
    current = date_debut

    while current <= date_fin:
        if current.weekday() != 6:  # exclure dimanche
            if current not in jours_vendus_agent:
                jours_absents.append(format_date_fr(current))
        current += timedelta(days=1)

    return jours_absents
