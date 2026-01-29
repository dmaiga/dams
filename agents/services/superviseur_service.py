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
from datetime import datetime
from django.utils import timezone

def get_periode_courante():
    now = timezone.now()
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return debut_mois, now



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
        KPI SUPERVISEUR – MOIS COURANT (SOURCE FIABLE)
        """
    
        date_debut, date_fin = get_periode_courante()
    
        # 1️⃣ NOMBRE D’AGENTS
        agents = Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=['terrain', 'agent_gros'],
            est_actif=True
        )
    
        nombre_agents = agents.count()
    
        # 2️⃣ MONTANT À RECOUVRER (argent encore chez les agents – MOIS)
        total_ventes_agents = Vente.objects.filter(
            agent__in=agents,
            date_vente__gte=date_debut,
            date_vente__lte=date_fin,
            est_supprime=False
        ).aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')),
                Decimal('0.00')
            )
        )['total']
    
        total_recouvre_agents = Recouvrement.objects.filter(
            agent__in=agents,
            superviseur=superviseur,
            date_recouvrement__gte=date_debut,
            date_recouvrement__lte=date_fin
        ).aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0.00'))
        )['total']
    
        montant_a_recouvrer = total_ventes_agents - total_recouvre_agents
            
    
    
        # 3️⃣ CASH DÉTENU PAR LE SUPERVISEUR (RÉEL)
        ventes_superviseur = Vente.objects.filter(
            agent=superviseur,
            date_vente__gte=date_debut,
            date_vente__lte=date_fin,
            est_supprime=False
        ).aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')),
                Decimal('0.00')
            )
        )['total']
    
        cash_detenu = (
            total_recouvre_agents
            + ventes_superviseur
        )
    
        # 4️⃣ MONTANT DÉJÀ REMIS AU ROT (MOIS)
        montant_remis_rot = RecouvrementSuperviseur.objects.filter(
            superviseur=superviseur,
            date_recouvrement__gte=date_debut,
            date_recouvrement__lte=date_fin
        ).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0.00'))
        )['total']
    
        # 🔥 CASH NET À DISPOSITION
        cash_detenu -= montant_remis_rot
    
        return {
            # KPI demandés
            'nombre_agents': nombre_agents,
            'montant_a_recouvrer': montant_a_recouvrer,
            'cash_detenu': cash_detenu,
            'montant_remis_rot': montant_remis_rot,
        }
    
    # =====================================================
    # DÉTAIL FINANCIER PAR AGENT (POST-CLÔTURE)
    # =====================================================
    @staticmethod
    def get_agents_financiers(superviseur):
        date_ref = superviseur.date_derniere_cloture
        date_debut, date_fin = get_periode_courante()

        agents = SuperviseurDashboardService.get_agents(superviseur)
        data = []

        for agent in agents:
            total_ventes = Vente.objects.filter(
                agent=agent,
                date_vente__gte=date_debut,
                date_vente__lte=date_fin
            ).aggregate(
                total=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')),
                    Decimal('0')
                )
            )['total']

            total_recouvre = Recouvrement.objects.filter(
                agent=agent,
                superviseur=superviseur,
                date_recouvrement__gte=date_debut,
                date_recouvrement__lte=date_fin
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
