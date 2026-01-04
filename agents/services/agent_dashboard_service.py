# agents/services/agent_dashboard_service.py

from django.utils import timezone
from django.db.models import F
from core.models import (
    Agent,
    Vente,
    DetailDistribution,
    Dette,
    BonusAgent,
)

class AgentDashboardService:
    """
    Service métier pour le tableau de bord Agent Terrain
    """

    def __init__(self, user):
        self.user = user
        self.agent = self._get_agent()

    # =========================
    # Initialisation
    # =========================
    def _get_agent(self):
        try:
            return Agent.objects.get(user=self.user)
        except Agent.DoesNotExist:
            return None

    # =========================
    # Méthode publique principale
    # =========================
    def get_dashboard_context(self):
        if not self.agent:
            return None

        bonus_agent, _ = BonusAgent.objects.get_or_create(agent=self.agent)

        ventes_mois = self._get_ventes_du_mois()
        produits_disponibles = self._get_stock_disponible()
        dettes_prioritaires = self._get_dettes_prioritaires(ventes_mois)
        ventes_recentes = self._get_ventes_recentes(ventes_mois)

        context = {
            'agent': self.agent,

            # Stats simples
            'nombre_ventes_mois': ventes_mois.count(),
            'clients_servis_mois': ventes_mois.values('client').distinct().count(),

            # Stock
            'produits_disponibles': produits_disponibles,
            'total_stock_disponible': sum(
                d.quantite_restante for d in produits_disponibles
            ),

            # Dettes
            'dettes_prioritaires': dettes_prioritaires,
            'total_a_recouvrer': sum(
                dette.montant_restant for dette in dettes_prioritaires
            ),

            # Activité
            'ventes_recentes': ventes_recentes,
        }

        return context

    # =========================
    # Méthodes internes
    # =========================
    def _get_ventes_du_mois(self):
        return Vente.objects.filter(
            agent=self.agent,
            date_vente__month=timezone.now().month,
            date_vente__year=timezone.now().year
        )

    def _get_stock_disponible(self):
        return (
            DetailDistribution.objects
            .filter(distribution__agent_terrain=self.agent)
            .annotate(
                quantite_restante=F('quantite') - F('quantite_vendue')
            )
            .filter(quantite_restante__gt=0)
            .select_related('lot__produit')
            .order_by('lot__produit__nom')[:10]
        )

    def _get_dettes_prioritaires(self, ventes_queryset):
        return Dette.objects.filter(
            vente__in=ventes_queryset,
            statut__in=['en_cours', 'partiellement_paye', 'en_retard']
        ).order_by('date_echeance')[:3]

    def _get_ventes_recentes(self, ventes_queryset):
        return (
            ventes_queryset
            .select_related('client', 'detail_distribution__lot__produit')
            .order_by('-date_vente')[:5]
        )
