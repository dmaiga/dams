from core.models import (
    LotEntrepot,
    Vente,
)


from collections import defaultdict

from core.models import (
    LotEntrepot,
    Vente,
)


class SurveillancePrixService:

    @staticmethod
    def get_resume():

        resultat = []

        lots = (
            LotEntrepot.objects
            .select_related(
                "produit",
                "fournisseur",
            )
        )

        for lot in lots:

            prix_achat = (
                lot.prix_achat_unitaire
            )

            ventes_rouges = (
                Vente.objects
                .filter(
                    detail_distribution__lot=lot,
                    est_supprime=False,
                    prix_vente_unitaire__lt=prix_achat,
                )
                .select_related(
                    "agent",
                )
            )

            if not ventes_rouges.exists():
                continue

            prix_min = min(
                vente.prix_vente_unitaire
                for vente in ventes_rouges
            )

            vendeurs = {
                vente.agent_id
                for vente in ventes_rouges
            }

            resultat.append({

                "lot": lot,

                "produit": lot.produit,

                "fournisseur": lot.fournisseur,

                "date_reception":
                    lot.date_reception,

                "quantite_initiale":
                    lot.quantite_initiale,

                "prix_achat":
                    prix_achat,

                "prix_min":
                    prix_min,

                "ecart":
                    prix_min - prix_achat,

                "nb_vendeurs":
                    len(vendeurs),

                "nb_ventes_rouges":
                    ventes_rouges.count(),

            })

        resultat.sort(
            key=lambda x: x["ecart"]
        )

        return {

            "stats": {

                "nb_lots_rouges":
                    len(resultat),

                "nb_ventes_rouges":
                    sum(
                        item["nb_ventes_rouges"]
                        for item in resultat
                    ),

                "nb_vendeurs_concernes":
                    sum(
                        item["nb_vendeurs"]
                        for item in resultat
                    ),
            },

            "lignes":
                resultat,
        }
 
    @staticmethod
    def get_detail_lot(lot):

        ventes = (
            Vente.objects
            .filter(
                detail_distribution__lot=lot,
                est_supprime=False
            )
            .select_related(
                "agent",
                "agent__superviseur",
            )
            .order_by("-date_vente")
        )

        lignes = []

        nb_ventes_rouges = 0

        for vente in ventes:

            prix_achat = (
                lot.prix_achat_unitaire
            )

            rouge = (
                vente.prix_vente_unitaire
                < prix_achat
            )

            if rouge:
                nb_ventes_rouges += 1

            lignes.append({

                "vente": vente,

                "agent":
                    vente.agent,

                "superviseur":
                    vente.agent.superviseur,

                "date":
                    vente.date_vente,

                "prix":
                    vente.prix_vente_unitaire,

                "quantite":
                    vente.quantite,

                "rouge":
                    rouge,

            })

        return {

            "lot": lot,

            "prix_achat":
                lot.prix_achat_unitaire,

            "produit":
                lot.produit,

            "fournisseur":
                lot.fournisseur,

            "date_reception":
                lot.date_reception,

            "quantite_initiale":
                lot.quantite_initiale,

            "nb_ventes_rouges":
                nb_ventes_rouges,

            "ventes":
                lignes,
        }