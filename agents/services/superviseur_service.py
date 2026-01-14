from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, F
from django.db.models.functions import Coalesce
from django.db import models
from core.models import (
    Agent,
    AffectationLotSuperviseur,
    DistributionAgent,
    Vente,
    Recouvrement,
    RecouvrementSuperviseur,
)

from datetime import timedelta
from django.utils import timezone

from core.models import (
    Agent,
    AffectationLotSuperviseur,
    DistributionAgent,
    Vente,
)


class SuperviseurDashboardService:
    """
    Dashboard SUPERVISEUR – nouveau workflow post-clôture
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
        return Agent.objects.filter(
            user=user,
            type_agent='entrepot',
            est_actif=True
        ).first()

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

            stock.setdefault(pid, {
                'produit': produit,
                'quantite_initiale': 0,
                'quantite_restante': 0,
            })

            stock[pid]['quantite_initiale'] += aff.quantite_initiale
            stock[pid]['quantite_restante'] += aff.quantite_restante

        return list(stock.values())

    # =====================================================
    # AGENTS TERRAIN
    # =====================================================
    @staticmethod
    def get_agents(superviseur):
        return Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=['terrain', 'agent_gros'],
            est_actif=True
        ).select_related('user')

    # =====================================================
    # FINANCES SUPERVISEUR (SOURCE = MODÈLE)
    # =====================================================
    @staticmethod
    def get_finances_superviseur(superviseur):
        """
        FINANCES SUPERVISEUR – POST-CLÔTURE
    
        Objectif :
        - montrer uniquement ce qui est utile à son activité terrain
        - refléter le cash réel détenu ou attendu
        """
    
        date_ref = superviseur.date_derniere_cloture
    
        # 1️⃣ VENTES DES AGENTS (argent généré sur le terrain)
        total_ventes_agents = Vente.objects.filter(
            agent__superviseur=superviseur,
            date_vente__gt=date_ref
        ).aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')),
                Decimal('0.00')
            )
        )['total']
    
        # 2️⃣ ARGENT DÉJÀ RÉCUPÉRÉ AUPRÈS DES AGENTS
        total_recouvre_agents = Recouvrement.objects.filter(
            superviseur=superviseur,
            date_recouvrement__gt=date_ref
        ).aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0.00'))
        )['total']
    
        # 3️⃣ VENTES PERSONNELLES AUTORISÉES DU SUPERVISEUR
        # 👉 auto-recouvrées (argent directement chez lui)
        ventes_superviseur = Vente.objects.filter(
            agent=superviseur,
            date_vente__gt=date_ref
        ).aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')),
                Decimal('0.00')
            )
        )['total']
    
        # 4️⃣ ARGENT DÉJÀ REMIS AU ROT (VENTE UNIQUEMENT)
        total_remis_rot = RecouvrementSuperviseur.objects.filter(
            superviseur=superviseur,
            date_creation__gt=date_ref
        ).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0.00'))
        )['total']
    
        # =====================
        # SOLDES MÉTIERS
        # =====================
    
        # 💵 Argent physiquement chez le superviseur
        argent_chez_superviseur = (
            total_recouvre_agents
            + ventes_superviseur
            - total_remis_rot
        )
    
        # 💸 Argent encore chez les agents
        reste_a_recouvrer = total_ventes_agents - total_recouvre_agents
    
        return {
            'date_derniere_cloture': date_ref,
    
            # flux terrain
            'total_ventes_agents': total_ventes_agents,
            'total_recouvre_agents': total_recouvre_agents,
            'ventes_superviseur': ventes_superviseur,
            'total_remis_rot': total_remis_rot,
    
            # soldes utiles
            'argent_chez_superviseur': argent_chez_superviseur,
            'reste_a_recouvrer': reste_a_recouvrer,
        }
    
    # =====================================================
    # DÉTAIL FINANCIER PAR AGENT (POST-CLÔTURE)
    # =====================================================
    @staticmethod
    def get_agents_financiers(superviseur):
        date_ref = superviseur.date_derniere_cloture
        agents = SuperviseurDashboardService.get_agents(superviseur)
        data = []

        for agent in agents:
            total_ventes = Vente.objects.filter(
                agent=agent,
                date_vente__gt=date_ref
            ).aggregate(
                total=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')),
                    Decimal('0')
                )
            )['total']

            total_recouvre = Recouvrement.objects.filter(
                agent=agent,
                superviseur=superviseur,
                date_recouvrement__gt=date_ref
            ).aggregate(
                total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
            )['total']

            reste = total_ventes - total_recouvre

            data.append({
                'agent': agent,
                'total_ventes': total_ventes,
                'total_recouvre': total_recouvre,
                'reste_a_rendre': reste,
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

            # Finances (post-clôture)
            'finances_superviseur': SuperviseurDashboardService.get_finances_superviseur(superviseur),

            # Détail agents
            'agents_financiers': SuperviseurDashboardService.get_agents_financiers(superviseur),

            # Activité
            'distributions_recentes': SuperviseurDashboardService.get_distributions_recentes(superviseur),
        }
