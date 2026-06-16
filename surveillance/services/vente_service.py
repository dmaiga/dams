from django.db.models import Sum

from core.models import Vente


class VenteSurveillanceService:

    @staticmethod
    def kg_vendus(date_debut,date_fin,superviseur=None,produit=None,):
        ventes = Vente.objects.filter(
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False
        )
        if superviseur:
            ventes = ventes.filter(
                agent__superviseur=superviseur
            )
        if produit:
            ventes = ventes.filter(
                detail_distribution__lot__produit=produit
            )
        total = sum(
            vente.quantite_en_kg
            for vente in ventes
        )

        return total