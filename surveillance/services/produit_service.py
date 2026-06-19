from decimal import Decimal

from django.db.models import Sum

from core.models import Produit, Vente
from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService,
)
from surveillance.services.vente_service import KG_EXPRESSION


def _kg_par_produit(date_debut, date_fin):
    """Retourne un dict {produit_id: kg_total} pour la période donnée."""
    rows = (
        Vente.objects
        .filter(
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False,
        )
        .values('detail_distribution__lot__produit')
        .annotate(kg=Sum(KG_EXPRESSION))
    )
    return {row['detail_distribution__lot__produit']: row['kg'] for row in rows}


class ProduitSurveillanceService:

    @staticmethod
    def variations_semaine():
        debut_actuel, fin_actuel = ComparaisonPeriodeService.semaine_actuelle()
        debut_prec, fin_prec = ComparaisonPeriodeService.semaine_precedente()

        # 2 requêtes d'agrégation (au lieu de 2N+2 auparavant)
        kg_actuel_map = _kg_par_produit(debut_actuel, fin_actuel)
        kg_prec_map = _kg_par_produit(debut_prec, fin_prec)

        produits = Produit.objects.all()

        resultat = []
        for produit in produits:
            kg_actuel = kg_actuel_map.get(produit.id, Decimal('0'))
            kg_prec = kg_prec_map.get(produit.id, Decimal('0'))
            variation = ComparaisonService.variation(kg_actuel, kg_prec)

            resultat.append({
                "produit": produit,
                "kg_actuel": kg_actuel,
                "kg_prec": kg_prec,
                "variation": round(variation, 2),
            })

        resultat.sort(key=lambda x: x["variation"])
        return resultat
