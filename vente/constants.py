# Seuils de la liste de surveillance des prix (page « Correcteurs ventes »).
#
# Source de vérité unique : surveillance.constants. Cette liste et l'alerte monitoring
# `prix_ecart_achat` partagent donc les mêmes seuils (alignés le 09/10/2026).
#   - marge faible : prix < achat + SEUIL_MARGE_MINIMALE (45 F)
#   - prix élevé   : prix > achat + SEUIL_ECART_PRIX_ACHAT
from surveillance.constants import SEUIL_ECART_PRIX_ACHAT, SEUIL_MARGE_MINIMALE  # noqa: F401

SEUIL_PRIX_ELEVE = SEUIL_ECART_PRIX_ACHAT
