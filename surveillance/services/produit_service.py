from core.models import Produit

from surveillance.services.vente_service import (
    VenteSurveillanceService
)

from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService
)


class ProduitSurveillanceService:

    @staticmethod
    def variations_semaine():

        resultat = []

        debut_actuel, fin_actuel = (
            ComparaisonPeriodeService.semaine_actuelle()
        )

        debut_prec, fin_prec = (
            ComparaisonPeriodeService.semaine_precedente()
        )

        produits = Produit.objects.all()

        for produit in produits:

            kg_actuel = (
                VenteSurveillanceService.kg_vendus(
                    debut_actuel,
                    fin_actuel,
                    produit=produit
                )
            )

            kg_prec = (
                VenteSurveillanceService.kg_vendus(
                    debut_prec,
                    fin_prec,
                    produit=produit
                )
            )

            variation = (
                ComparaisonService.variation(
                    kg_actuel,
                    kg_prec
                )
            )

            resultat.append({
                "produit": produit,
                "kg_actuel": kg_actuel,
                "kg_prec": kg_prec,
                "variation": round(variation, 2),
            })

        resultat.sort(
            key=lambda x: x["variation"]
        )

        return resultat