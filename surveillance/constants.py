from datetime import date

# Début des données de vente fiables pour tout le thème Volumes (Kg vendus) :
# liste_kg_service, superviseur_service, produit_service, detail_produit_service,
# detail_superviseur_service. Utilisée via max(date_selectionnee, DATE_PLANCHER_VENTES),
# jamais seule : on ne redescend jamais avant cette date quelle que soit la période choisie.
DATE_PLANCHER_VENTES = date(2026, 1, 1)

# Plancher pour la détection des anomalies de prix (ventes sous le prix d'achat)
# dans PrixSurveillanceService / SurveillancePrixService : seules les ventes
# postérieures à cette date sont examinées.
DATE_PLANCHER_PRIX   = date(2026, 7, 1)

# Plancher pour les deux alertes de StockAgeService (rotation lente, stock dormant) :
# ignore les lots/distributions/affectations antérieurs à cette date, jugés trop
# anciens/peu fiables pour ce type de détection.
DATE_PLANCHER_STOCK  = date(2026, 7, 1)

# Rotation lente : nombre de jours sans vente sur un lot distribué avant alerte.
DELAI_ROTATION_JOURS = 5

# Stock dormant : nombre de jours en entrepôt/chez le superviseur sans distribution
# avant alerte.
DELAI_STOCK_DORMANT_JOURS = 15
