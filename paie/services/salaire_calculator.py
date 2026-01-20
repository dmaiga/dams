from decimal import Decimal
from django.db.models import Sum, Max, F, DecimalField, ExpressionWrapper, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Agent, Vente, Recouvrement
from django.db.models import Value

class CalculatorSalaire:
    """
    Service – Calcul du salaire d’un agent
    """

    @staticmethod
    def calcul_salaire_mamy(agent, date_debut, date_fin, salaire_base=Decimal("20000")):
        ventes = Vente.objects.filter(
            agent=agent,
            date_vente__date__range=(date_debut, date_fin),
            est_supprime=False,
        ).annotate(
            kilo_ligne=F("quantite") *
            Coalesce(
                F("detail_distribution__lot__produit__poids_unitaire_kg"),
                Decimal("1")
            )
        )

        kilo_total = ventes.aggregate(
            total=Coalesce(Sum("kilo_ligne"), Decimal("0"))
        )["total"]

        incentive = kilo_total * Decimal("25")

        return {
            "salaire_base": salaire_base,
            "incentive": incentive,
            "salaire_total": salaire_base + incentive,
            "kilo_total": kilo_total,
        }

    @staticmethod
    def calcul_salaire_gros(agent, date_debut, date_fin):
        ventes = Vente.objects.filter(
            agent=agent,
            date_vente__date__range=(date_debut, date_fin),
            est_supprime=False,
        )

        cartons = ventes.aggregate(
            total=Coalesce(Sum("quantite"), Decimal("0"))
        )["total"]

        if cartons < 150:
            salaire = cartons * Decimal("250")
        elif cartons < 200:
            salaire = Decimal("50000")
        else:
            salaire = Decimal("90000")

        return {
            "cartons": cartons,
            "salaire_total": salaire,
        }

    @staticmethod
    def calcul_salaire_superviseur(superviseur, date_debut, date_fin):
        salaire_base = Decimal("50000")
        dotation = Decimal("15000")

        agents = Agent.objects.filter(
            superviseur=superviseur,
            type_agent="terrain",
            est_actif=True
        )

        incentive_agents = Decimal("0")

        for agent in agents:
            data = CalculatorSalaire.calcul_salaire_mamy(agent, date_debut, date_fin)
            incentive_agents += data["incentive"]

        bonus = incentive_agents * Decimal("0.03")

        return {
            "salaire_base": salaire_base,
            "dotation": dotation,
            "bonus": bonus,
            "salaire_total": salaire_base + dotation + bonus,
        }
