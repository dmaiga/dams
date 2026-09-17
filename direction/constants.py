# Seuils d'ancienceté pour direction.suivi_distributions (sprint-14, 17/09/2026) : un produit
# sorti du dépôt sans vente enregistrée derrière lui devient suspect avec le temps — décision
# mdmaiga, "une semaine ça va, deux semaines c'est suspect". Distincts des seuils
# surveillance/constants.py (alerte opérationnelle courte, 3 jours) : usage différent, page
# d'investigation direction à horizon 1-2 semaines.

SEUIL_ATTENTION_JOURS = 7
SEUIL_CRITIQUE_JOURS = 14
