ALERTES_MVP = {
    "solde":            {"reenvoi_heures": 24},   # réconciliation matinale, se répète chaque jour tant que solde > seuil
    "solde_persistant": {"reenvoi_heures": 24},   # critique — ne doit pas se perdre
    "stock":            {"reenvoi_heures": None}, # une seule notification, silence tant qu'ACTIVE
    "prix":             {"reenvoi_heures": None},
    "activite":         {"reenvoi_heures": 12},   # deux rappels par jour si agent toujours inactif
}
