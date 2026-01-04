from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, F
from django.db.models.functions import Coalesce

from core.models import (
    Agent,
    AffectationLotSuperviseur,
    DistributionAgent,
    Vente,
    Recouvrement,
    RecouvrementSuperviseur,
)


class SuperviseurDashboardService:
    """
    Dashboard SUPERVISEUR – nouveau workflow
    Le superviseur :
    - distribue le stock
    - recouvre l'argent auprès des agents
    - remet l'argent au ROT
    """

    # =====================================================
    # SUPERVISEUR COURANT
    # =====================================================
    @staticmethod
    def get_superviseur(user):
        try:
            return Agent.objects.get(
                user=user,
                type_agent='entrepot',
                est_actif=True
            )
        except Agent.DoesNotExist:
            return None

    # =====================================================
    # STOCK ATTRIBUÉ AU SUPERVISEUR
    # =====================================================
    @staticmethod
    def get_stock_superviseur(superviseur):
        affectations = (
            AffectationLotSuperviseur.objects
            .filter(superviseur=superviseur)
            .select_related('lot__produit')
        )

        stock = {}

        for aff in affectations:
            produit = aff.lot.produit
            pid = produit.id

            if pid not in stock:
                stock[pid] = {
                    'produit': produit,
                    'quantite_initiale': Decimal('0'),
                    'quantite_restante': Decimal('0'),
                }

            stock[pid]['quantite_initiale'] += aff.quantite_initiale
            stock[pid]['quantite_restante'] += aff.quantite_restante

        return list(stock.values())

    # =====================================================
    # AGENTS TERRAIN SOUS SA RESPONSABILITÉ
    # =====================================================
    @staticmethod
    def get_agents(superviseur):
        return Agent.objects.filter(
            superviseur=superviseur,
            type_agent='terrain',
            est_actif=True
        ).select_related('user')

    # =====================================================
    # ARGENT : VENTES TOTALES DES AGENTS
    # =====================================================
    @staticmethod
    def get_total_ventes_agents(superviseur):
        return Vente.objects.filter(
            agent__superviseur=superviseur
        ).aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')),
                Decimal('0')
            )
        )['total']

    # =====================================================
    # ARGENT : TOTAL RECUPÉRÉ PAR LE SUPERVISEUR
    # =====================================================
    @staticmethod
    def get_total_recouvre(superviseur):
        return Recouvrement.objects.filter(
            superviseur=superviseur
        ).aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
        )['total']

    # =====================================================
    # ARGENT : TOTAL REMIS AU ROT
    # =====================================================
    @staticmethod
    def get_total_remis_rot(superviseur):
        return RecouvrementSuperviseur.objects.filter(
            superviseur=superviseur
        ).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']

    # =====================================================
    # FINANCES SUPERVISEUR (LECTURE CLAIRE)
    # =====================================================
    @staticmethod
    def get_finances_superviseur(superviseur):
        total_ventes = SuperviseurDashboardService.get_total_ventes_agents(superviseur)
        total_recouvre = SuperviseurDashboardService.get_total_recouvre(superviseur)
        total_remis_rot = SuperviseurDashboardService.get_total_remis_rot(superviseur)

        return {
            # Argent global généré par ses agents
            'total_ventes_agents': total_ventes,

            # Argent encore CHEZ LES AGENTS
            'reste_a_recouvrer': total_ventes - total_recouvre,

            # Argent collecté par le superviseur
            'total_recouvre': total_recouvre,

            # Argent déjà remis au ROT
            'total_remis_rot': total_remis_rot,

            # Argent PHYSIQUEMENT chez le superviseur
            'argent_chez_superviseur': total_recouvre - total_remis_rot,
        }

    # =====================================================
    # DÉTAIL FINANCIER PAR AGENT
    # =====================================================
    @staticmethod
    def get_agents_financiers(superviseur):
        agents = SuperviseurDashboardService.get_agents(superviseur)
        data = []

        for agent in agents:
            total_ventes = Vente.objects.filter(
                agent=agent
            ).aggregate(
                total=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')),
                    Decimal('0')
                )
            )['total']

            total_recouvre = Recouvrement.objects.filter(
                agent=agent,
                superviseur=superviseur
            ).aggregate(
                total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
            )['total']

            data.append({
                'agent': agent,
                'total_ventes': total_ventes,
                'total_recouvre': total_recouvre,
                'reste_a_rendre': total_ventes - total_recouvre,
            })

        return data

    # =====================================================
    # ACTIVITÉ RÉCENTE
    # =====================================================
    @staticmethod
    def get_distributions_recentes(superviseur, jours=7):
        date_min = timezone.now() - timedelta(days=jours)
        return DistributionAgent.objects.filter(
            superviseur=superviseur,
            date_distribution__gte=date_min
        ).count()

    # =====================================================
    # BUILD DASHBOARD
    # =====================================================
    @staticmethod
    def build_dashboard_perimetre(user):
        superviseur = SuperviseurDashboardService.get_superviseur(user)
        if not superviseur:
            return None

        return {
            'superviseur': superviseur,

            # Stock
            'stock_superviseur': SuperviseurDashboardService.get_stock_superviseur(superviseur),

            # Agents
            'agents_terrain': SuperviseurDashboardService.get_agents(superviseur),

            # Finances globales
            'finances_superviseur': SuperviseurDashboardService.get_finances_superviseur(superviseur),

            # Détail par agent
            'agents_financiers': SuperviseurDashboardService.get_agents_financiers(superviseur),

            # Activité
            'distributions_recentes': SuperviseurDashboardService.get_distributions_recentes(superviseur),
        }
