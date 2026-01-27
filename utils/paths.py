import os

MOIS_FR = {
    1: "janvier", 2: "fevrier", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "aout",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "decembre",
}

def chemin_rapport(base_dir, date_debut):
    annee = str(date_debut.year)
    mois = MOIS_FR[date_debut.month]

    path = os.path.join(base_dir, annee, mois)
    os.makedirs(path, exist_ok=True)

    return path
