ALERTES_MVP = {
    "solde":              {"reenvoi_heures": 24},   # réconciliation matinale, se répète chaque jour tant que solde > seuil
    "solde_persistant":   {"reenvoi_heures": 24},   # critique — ne doit pas se perdre
    "stock_entrepot":     {"reenvoi_heures": None}, # une seule notification, silence tant qu'ACTIVE
    # Rappel toutes les 48 h (décision mdmaiga, 08/09/2026) : la liste du stock
    # dormant superviseur/agent ne retombe jamais à zéro, donc l'alerte ne se
    # résout jamais — sans rappel, un seul message était envoyé puis plus rien.
    "stock_superviseur":  {"reenvoi_heures": 48},
    "stock_agent":        {"reenvoi_heures": 48},
    "prix":               {"reenvoi_heures": None},
    "activite":           {"reenvoi_heures": 48},   # un rappel tous les deux jours si toujours inactif
}
