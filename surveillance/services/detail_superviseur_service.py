from decimal import Decimal

from django.db.models import Count, Sum

from core.models import Agent, Produit, Vente
from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService,
)
from surveillance.services.vente_service import KG_EXPRESSION


class DetailSuperviseurService:

    @staticmethod
    def get_data(superviseur):
        debut_actuel, fin_actuel = ComparaisonPeriodeService.semaine_actuelle()
        debut_prec, fin_prec = ComparaisonPeriodeService.semaine_precedente()

        base = dict(agent__superviseur=superviseur, est_supprime=False)

        # 2 requêtes d'agrégation scalaire
        kg_actuel = (
            Vente.objects
            .filter(**base, date_vente__date__gte=debut_actuel, date_vente__date__lte=fin_actuel)
            .aggregate(total=Sum(KG_EXPRESSION))['total']
            or Decimal('0')
        )
        kg_prec = (
            Vente.objects
            .filter(**base, date_vente__date__gte=debut_prec, date_vente__date__lte=fin_prec)
            .aggregate(total=Sum(KG_EXPRESSION))['total']
            or Decimal('0')
        )

        variation = ComparaisonService.variation(kg_actuel, kg_prec)

        # 1 requête : kg + nb produits distincts par agent
        agent_rows = (
            Vente.objects
            .filter(
                **base,
                date_vente__date__gte=debut_actuel,
                date_vente__date__lte=fin_actuel,
            )
            .values('agent')
            .annotate(
                kg=Sum(KG_EXPRESSION),
                nb_produits=Count(
                    'detail_distribution__lot__produit',
                    distinct=True,
                ),
            )
            .order_by('-kg')
        )

        agent_ids = [r['agent'] for r in agent_rows]
        agents_map = {a.id: a for a in Agent.objects.filter(id__in=agent_ids)}

        agents_stats = [
            {
                "agent": agents_map[r['agent']],
                "kg": r['kg'],
                "nb_produits": r['nb_produits'],
            }
            for r in agent_rows
            if r['agent'] in agents_map
        ]

        # 1 requête : kg groupé par produit
        produit_rows = (
            Vente.objects
            .filter(
                **base,
                date_vente__date__gte=debut_actuel,
                date_vente__date__lte=fin_actuel,
            )
            .values('detail_distribution__lot__produit')
            .annotate(kg=Sum(KG_EXPRESSION))
            .order_by('-kg')
        )

        produit_ids = [r['detail_distribution__lot__produit'] for r in produit_rows]
        produits_map = {p.id: p for p in Produit.objects.filter(id__in=produit_ids)}

        produits_stats = [
            {
                "produit": produits_map[r['detail_distribution__lot__produit']],
                "kg": r['kg'],
            }
            for r in produit_rows
            if r['detail_distribution__lot__produit'] in produits_map
        ]

        return {
            "superviseur": superviseur,
            "kg_actuel": round(kg_actuel, 2),
            "kg_prec": round(kg_prec, 2),
            "variation": round(variation, 2),
            "agents_stats": agents_stats,
            "produits_stats": produits_stats,
        }
