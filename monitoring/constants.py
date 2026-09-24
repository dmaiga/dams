ALERTES_MVP = {
    "solde":              {"reenvoi_heures": 24},   # réconciliation matinale, se répète chaque jour tant que solde > seuil
    "solde_persistant":   {"reenvoi_heures": 24},   # critique — ne doit pas se perdre
    "stock_entrepot":     {"reenvoi_heures": None}, # une seule notification, silence tant qu'ACTIVE
    # Rappel quotidien (24h) — passé de 48h à 24h le 24/09/2026 à la demande de
    # mdmaiga : la liste du stock dormant superviseur/agent ne retombe jamais à
    # zéro, donc l'alerte ne se résout jamais — sans rappel, un seul message
    # était envoyé puis plus rien.
    "stock_superviseur":  {"reenvoi_heures": 24},   # quotidien (demande mdmaiga 24/09/2026)
    "stock_agent":        {"reenvoi_heures": 24},   # quotidien (demande mdmaiga 24/09/2026)
    "prix":               {"reenvoi_heures": None},
    "prix_ecart_achat":   {"reenvoi_heures": None},  # ajouté 24/09/2026, cf. moteur_alerte.py
    "activite":           {"reenvoi_heures": 24},   # quotidien (demande mdmaiga 24/09/2026)
}

# Descriptions destinées aux destinataires des alertes Telegram (superviseurs, direction) —
# insérées directement dans le corps du message, sous le titre. Rédigées en langage métier,
# sans référence au code ni aux décisions internes : ce texte peut être lu tel quel par
# n'importe quel destinataire externe à l'équipe technique.
DESCRIPTIONS_ALERTES = {
    "solde": (
        "Superviseurs dont le cash non remis dépasse le seuil d'alerte (30 000 FCFA). "
        "Envoyé chaque jour tant qu'au moins un superviseur reste concerné."
    ),
    "solde_persistant": (
        "Solde d'un superviseur resté positif après 3 remises consécutives, sans se résorber. "
        "Envoyé chaque jour tant que la situation n'est pas résolue."
    ),
    "stock_entrepot": (
        "Produits reçus à l'entrepôt central depuis plus de 15 jours, toujours non distribués. "
        "Notification unique à la détection, sans rappel automatique."
    ),
    "stock_superviseur": (
        "Produits remis à ce superviseur depuis plus de 3 jours, toujours non redistribués à un agent. "
        "Envoyé chaque jour tant que la situation persiste."
    ),
    "stock_agent": (
        "Produits remis aux agents de ce superviseur depuis plus de 3 jours, toujours non vendus. "
        "Envoyé chaque jour tant que la situation persiste."
    ),
    "prix": (
        "Ventes enregistrées avec une marge inférieure à 45 FCFA par unité — risque de vente à perte "
        "ou de prix mal saisi. Notification unique à la détection, sans rappel automatique."
    ),
    "prix_ecart_achat": (
        "Ventes enregistrées à un prix supérieur de plus de 2 500 FCFA au prix d'achat — à vérifier "
        "(bonne négociation ou erreur de saisie). Notification unique à la détection, sans rappel "
        "automatique."
    ),
    "activite": (
        "Agents de ce superviseur sans vente enregistrée depuis plus de 3 jours. "
        "Envoyé chaque jour tant que la situation persiste."
    ),
}
