from decimal import Decimal

from django.db.models import Sum

from core.models import Agent, Vente
from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService,
)
from surveillance.services.vente_service import KG_EXPRESSION


class DetailProduitService:

    @staticmethod
    def get_data(produit, debut_semaine=None):
        from surveillance.constants import DATE_PLANCHER_VENTES
        if debut_semaine:
            debut_actuel, fin_actuel = ComparaisonPeriodeService.semaine(debut_semaine)
            debut_prec, fin_prec = ComparaisonPeriodeService.semaine_prec(debut_semaine)
        else:
            debut_actuel, fin_actuel = ComparaisonPeriodeService.semaine_actuelle()
            debut_prec, fin_prec = ComparaisonPeriodeService.semaine_precedente()

        base = dict(
            detail_distribution__lot__produit=produit,
            est_supprime=False,
        )

        # 2 requêtes d'agrégation scalaire
        kg_actuel = (
            Vente.objects
            .filter(**base, date_vente__date__gte=max(debut_actuel, DATE_PLANCHER_VENTES), date_vente__date__lte=fin_actuel)
            .aggregate(total=Sum(KG_EXPRESSION))['total']
            or Decimal('0')
        )
        kg_prec = (
            Vente.objects
            .filter(**base, date_vente__date__gte=max(debut_prec, DATE_PLANCHER_VENTES), date_vente__date__lte=fin_prec)
            .aggregate(total=Sum(KG_EXPRESSION))['total']
            or Decimal('0')
        )

        variation = ComparaisonService.variation(kg_actuel, kg_prec)

        # 1 requête : kg groupé par superviseur
        sup_rows = (
            Vente.objects
            .filter(
                **base,
                date_vente__date__gte=max(debut_actuel, DATE_PLANCHER_VENTES),
                date_vente__date__lte=fin_actuel,
                agent__superviseur__isnull=False,
            )
            .values('agent__superviseur')
            .annotate(kg=Sum(KG_EXPRESSION))
            .order_by('-kg')
        )

        sup_ids = [r['agent__superviseur'] for r in sup_rows]
        sups_map = {s.id: s for s in Agent.objects.filter(id__in=sup_ids)}

        superviseurs_stats = [
            {
                "superviseur": sups_map[r['agent__superviseur']],
                "kg": r['kg'],
            }
            for r in sup_rows
            if r['agent__superviseur'] in sups_map
        ]

        # 1 requête : kg groupé par agent
        agent_rows = (
            Vente.objects
            .filter(
                **base,
                date_vente__date__gte=max(debut_actuel, DATE_PLANCHER_VENTES),
                date_vente__date__lte=fin_actuel,
            )
            .values('agent')
            .annotate(kg=Sum(KG_EXPRESSION))
            .order_by('-kg')
        )

        agent_ids = [r['agent'] for r in agent_rows]
        agents_map = {
            a.id: a
            for a in Agent.objects.filter(id__in=agent_ids).select_related('superviseur')
        }

        agents_stats = [
            {
                "agent": agents_map[r['agent']],
                "superviseur": agents_map[r['agent']].superviseur,
                "kg": r['kg'],
            }
            for r in agent_rows
            if r['agent'] in agents_map
        ]

        return {
            "produit": produit,
            "kg_actuel": round(kg_actuel, 2),
            "kg_prec": round(kg_prec, 2),
            "variation": round(variation, 2),
            "superviseurs_stats": superviseurs_stats,
            "agents_stats": agents_stats,
        }
