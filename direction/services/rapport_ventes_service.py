from django.db.models import Sum, Count
from django.utils import timezone
from core.models import Agent, Vente

from django.db.models import Sum, Count

class RapportVentesService:
    @staticmethod
    def rapport_agents(date_debut, date_fin):

        ventes = (
            Vente.objects
            .filter(
                date_vente__date__range=(date_debut, date_fin),
                agent__est_actif=True,
                est_supprime=False
            )
            .values(
                "agent__id",
                "agent__user__first_name",
                "agent__user__last_name",
                "date_vente__date", 
                "detail_distribution__lot__produit__nom"
            )
            .annotate(
                total_quantite=Sum("quantite"),
                nombre_ventes=Count("id")
            )
            .order_by(
                "agent__user__last_name",
                "date_vente__date"
            )
        )

        return ventes
