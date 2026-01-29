from django.db.models import (
    Sum, F, Count, DecimalField, ExpressionWrapper
)
from django.db.models.functions import Coalesce
from decimal import Decimal
from core.models import Vente


class AnalyseOperationnelleService:
    """
    Analyse opérationnelle terrain
    Source unique : Vente
    """

    @staticmethod
    def analyser(date_debut, date_fin, agent_id=None, produit_id=None):

        qs = (
            Vente.objects
            .filter(
                date_vente__date__gte=date_debut,
                date_vente__date__lte=date_fin,
                est_supprime=False
            )
            .select_related(
                'agent',
                'detail_distribution__lot__produit'
            )
        )

        # 🔎 Filtres optionnels
        if agent_id:
            qs = qs.filter(agent_id=agent_id)

        if produit_id:
            qs = qs.filter(
                detail_distribution__lot__produit_id=produit_id
            )

        # ============================
        # EXPRESSIONS DB
        # ============================
        ca_expr = ExpressionWrapper(
            F('quantite') * F('prix_vente_unitaire'),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        cout_expr = ExpressionWrapper(
            F('quantite') * F('detail_distribution__lot__prix_achat_unitaire'),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        kg_expr = ExpressionWrapper(
            F('quantite') * Coalesce(
                F('detail_distribution__lot__produit__poids_unitaire_kg'),
                Decimal('1')
            ),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        marge_expr = ca_expr - cout_expr

        # ============================
        # 1️⃣ KPIs GLOBAUX
        # ============================
        kpis = qs.aggregate(
            total_quantite=Coalesce(Sum('quantite'), Decimal('0.00')),
            total_kg=Coalesce(Sum(kg_expr), Decimal('0.00')),
            total_ca=Coalesce(Sum(ca_expr), Decimal('0.00')),
            total_marge=Coalesce(Sum(marge_expr), Decimal('0.00')),
            agents_contributeurs=Count('agent', distinct=True),
            produits_vendus=Count(
                'detail_distribution__lot__produit',
                distinct=True
            )
        )

        # ============================
        # 2️⃣ RÉCAP PAR PRODUIT
        # ============================
        recap_produits = (
            qs
            .values('detail_distribution__lot__produit__nom')
            .annotate(
                quantite=Coalesce(Sum('quantite'), Decimal('0.00')),
                kg_vendus=Coalesce(Sum(kg_expr), Decimal('0.00')),
                ca=Coalesce(Sum(ca_expr), Decimal('0.00')),
                marge=Coalesce(Sum(marge_expr), Decimal('0.00')),
            )
            .order_by('-kg_vendus')
        )

        # ============================
        # 3️⃣ RÉCAP PAR AGENT
        # ============================
        recap_agents = (
            qs
            .values(
                'agent__id',
                'agent__user__first_name',
                'agent__user__last_name'
            )
            .annotate(
                quantite=Coalesce(Sum('quantite'), Decimal('0.00')),
                kg_vendus=Coalesce(Sum(kg_expr), Decimal('0.00')),
                ca=Coalesce(Sum(ca_expr), Decimal('0.00')),
                marge=Coalesce(Sum(marge_expr), Decimal('0.00')),
                produits_vendus=Count(
                    'detail_distribution__lot__produit',
                    distinct=True
                )
            )
            .order_by('-kg_vendus')
        )

        return {
            'kpis': kpis,
            'recap_produits': recap_produits,
            'recap_agents': recap_agents,
        }
