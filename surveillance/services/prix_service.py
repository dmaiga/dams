from collections import defaultdict

from core.models import Vente


class PrixSurveillanceService:

    @staticmethod
    def ventes_a_perte():

        ventes = (
            Vente.objects
            .select_related(
                "detail_distribution__lot__produit",
                "detail_distribution__lot__fournisseur",
                "agent__superviseur",
            )
        )

        lots_rouges = defaultdict(list)

        for vente in ventes:

            lot = vente.detail_distribution.lot

            if vente.prix_vente_unitaire < lot.prix_achat_unitaire:
                lots_rouges[lot.id].append(vente)

        resultat = []

        for ventes_lot in lots_rouges.values():

            lot = ventes_lot[0].detail_distribution.lot

            prix_min = min(
                v.prix_vente_unitaire
                for v in ventes_lot
            )

            vendeurs = {
                v.agent.id: v.agent
                for v in ventes_lot
            }

            resultat.append({
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "date_reception": lot.date_reception,
                "quantite_initiale": lot.quantite_initiale,
                "prix_achat": lot.prix_achat_unitaire,
                "prix_min": prix_min,
                "ecart": prix_min - lot.prix_achat_unitaire,
                "nb_vendeurs": len(vendeurs),
                "vendeurs": list(vendeurs.values()),
                "nb_ventes_rouges": len(ventes_lot),
            })

        resultat.sort(
            key=lambda x: x["ecart"]
        )

        return resultat