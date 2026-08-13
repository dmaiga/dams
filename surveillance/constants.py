from datetime import date

# Début des données de vente fiables pour tout le thème Volumes (Kg vendus) :
# liste_kg_service, superviseur_service, produit_service, detail_produit_service,
# detail_superviseur_service. Utilisée via max(date_selectionnee, DATE_PLANCHER_VENTES),
# jamais seule : on ne redescend jamais avant cette date quelle que soit la période choisie.
DATE_PLANCHER_VENTES = date(2026, 1, 1)

# Plancher pour la détection des anomalies de prix (ventes sous la marge minimale)
# dans PrixSurveillanceService / SurveillancePrixService : seules les ventes
# postérieures à cette date sont examinées.
DATE_PLANCHER_PRIX   = date(2026, 7, 1)

# Plancher pour StockAgeService (activité commerciale, stock dormant/en rétention) :
# ignore les distributions/affectations antérieures à cette date, jugées trop
# anciennes/peu fiables pour ce type de détection.
DATE_PLANCHER_STOCK  = date(2026, 7, 1)

# Activité commerciale : nombre de jours sans vente VALIDE (tous lots confondus,
# dernière vente globale de l'agent) avant alerte. Décorrélé du stock/lot — voir
# Ne pas confondre avec la rétention de
# stock (DELAI_RETENTION_ACTEURS_JOURS) ni avec DELAI_STOCK_DORMANT_JOURS.
DELAI_ACTIVITE_COMMERCIALE_JOURS = 3

# Stock dormant à l'entrepôt central : nombre de jours en entrepôt sans
# affectation avant alerte.
DELAI_STOCK_DORMANT_JOURS = 15

# Rétention de stock chez un acteur commercial (superviseur, agent terrain/gros)
# après réception/mise à disposition : nombre de jours avant alerte. Seuil
# volontairement plus court qu'à l'entrepôt (l'acteur commercial doit écouler
# vite ce qu'il reçoit).
DELAI_RETENTION_ACTEURS_JOURS = 3

# Marge minimale attendue par vente unitaire (FCFA) — en-deçà, la vente est une
# anomalie ("vente rouge"). Source de vérité unique : PrixSurveillanceService et
# SurveillancePrixService doivent l'importer d'ici plutôt que la redéfinir
# localement (dette historique corrigée le 2026-08-13 — les deux définissaient
# chacun leur propre valeur, jamais alignée sur celle-ci).
SEUIL_MARGE_MINIMALE = 45
