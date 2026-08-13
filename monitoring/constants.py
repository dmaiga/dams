ALERTES_MVP = {
    "solde":              {"reenvoi_heures": 24},   # réconciliation matinale, se répète chaque jour tant que solde > seuil
    "solde_persistant":   {"reenvoi_heures": 24},   # critique — ne doit pas se perdre
    "stock_entrepot":     {"reenvoi_heures": None}, # une seule notification, silence tant qu'ACTIVE
    "stock_superviseur":  {"reenvoi_heures": None},
    "stock_agent":        {"reenvoi_heures": None},
    "prix":               {"reenvoi_heures": None},
    "activite":           {"reenvoi_heures": 48},   # un rappel tous les deux jours si toujours inactif
}
