from decimal import Decimal

from django.db.models import Count, Sum

from core.models import Agent, Produit, Vente
from surveillance.services.vente_service import KG_EXPRESSION


class ListeKgVenduService:

    @staticmethod
    def get_kpis(date_debut, date_fin):
        kg_total = (
            Vente.objects
            .filter(
                date_vente__date__gte=date_debut,
                date_vente__date__lte=date_fin,
                est_supprime=False,
            )
            .aggregate(total=Sum(KG_EXPRESSION))['total']
            or Decimal('0')
        )

        return {
            "kg_total": kg_total,
            "nb_superviseurs": Agent.objects.filter(
                type_agent="entrepot",
                est_actif=True,
            ).count(),
            "nb_agents": Agent.objects.filter(
                type_agent__in=["terrain", "agent_gros", "agent_polivalent"],
                est_actif=True,
            ).count(),
            "nb_produits": Produit.objects.count(),
        }

    @staticmethod
    def get_superviseurs(date_debut, date_fin):
        # 1 requête : kg total groupé par superviseur
        kg_rows = (
            Vente.objects
            .filter(
                date_vente__date__gte=date_debut,
                date_vente__date__lte=date_fin,
                est_supprime=False,
                agent__superviseur__isnull=False,
            )
            .values('agent__superviseur')
            .annotate(kg=Sum(KG_EXPRESSION))
        )
        kg_par_sup = {row['agent__superviseur']: row['kg'] for row in kg_rows}

        # 1 requête : superviseurs avec count d'agents géré via annotation
        superviseurs = (
            Agent.objects
            .filter(type_agent="entrepot", est_actif=True)
            .annotate(agents_count=Count('agents_geres'))
        )

        resultat = [
            {
                "superviseur": sup,
                "kg": kg_par_sup.get(sup.id, Decimal('0')),
                "agents_count": sup.agents_count,
            }
            for sup in superviseurs
        ]

        resultat.sort(key=lambda x: x["kg"], reverse=True)
        return resultat

    @staticmethod
    def get_agents(date_debut, date_fin, superviseur=None, produit=None):
        qs = Vente.objects.filter(
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False,
        )
        if superviseur:
            qs = qs.filter(agent__superviseur_id=superviseur)
        if produit:
            qs = qs.filter(detail_distribution__lot__produit_id=produit)

        # 1 requête : kg groupé par agent, trié en DB
        rows = (
            qs
            .values('agent')
            .annotate(kg=Sum(KG_EXPRESSION))
            .order_by('-kg')
        )

        # 1 requête : hydratation des objets Agent avec superviseur en 1 JOIN
        agent_ids = [r['agent'] for r in rows]
        agents_map = {
            a.id: a
            for a in Agent.objects.filter(id__in=agent_ids).select_related('superviseur')
        }

        return [
            {
                "agent": agents_map[r['agent']],
                "superviseur": agents_map[r['agent']].superviseur,
                "kg": r['kg'],
            }
            for r in rows
            if r['agent'] in agents_map
        ]
