# Seuils d'ancienceté pour direction.suivi_distributions (sprint-14, 17/09/2026) : un produit
# sorti du dépôt sans vente enregistrée derrière lui devient suspect avec le temps — décision
# mdmaiga, "une semaine ça va, deux semaines c'est suspect". Distincts des seuils
# surveillance/constants.py (alerte opérationnelle courte, 3 jours) : usage différent, page
# d'investigation direction à horizon 1-2 semaines.

SEUIL_ATTENTION_JOURS = 7
SEUIL_CRITIQUE_JOURS = 14

# Point de départ du suivi terrain (sprint-14) : les distributions antérieures à cette
# date n'ont pas été saisies avec la rigueur nécessaire pour ce suivi — on ignore ce bruit
# historique plutôt que de remonter une "investigation" sur des données non fiables.
from datetime import date

DATE_DEBUT_SUIVI_TERRAIN = date(2026, 7, 1)
