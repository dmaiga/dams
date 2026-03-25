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

def get_date_operationnelle(superviseur):
    """
    Date de référence opérationnelle :
    - dernière clôture si elle existe
    - sinon aucune limite (date.min)
    """
    return superviseur.date_derniere_cloture



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
            .order_by('lot__produit')
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
    # FINANCES SUPERVISEUR – DASHBOARD OPÉRATIONNEL
    # =====================================================
    @staticmethod
    def get_finances_superviseur(superviseur):
        """
        Dashboard superviseur – MOIS COURANT

        Définitions métier :
        - montant_a_recouvrer : argent encore chez les agents
        - cash_detenu : argent physiquement détenu par le superviseur
        (recouvrements + ventes perso – remises ROT)
        """

        # 🔹 Références temporelles
        date_debut, date_fin = get_periode_courante()
        date_ref = get_date_operationnelle(superviseur)

        # =====================================================
        # 1️⃣ AGENTS ACTIFS DU SUPERVISEUR
        # =====================================================
        agents = Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=["terrain", "agent_gros"],
            est_actif=True
        )

        nombre_agents = agents.count()

        # =====================================================
        # 2️⃣ MONTANT À RECOUVRER (ARGENT ENCORE CHEZ LES AGENTS)
        # =====================================================

        # Total des ventes réalisées par les agents sur la période
        total_ventes_agents = Vente.objects.filter(
            agent__in=agents,
            date_vente__gte=date_debut,
            date_vente__lte=date_fin,
            est_supprime=False
        ).aggregate(
            total=Coalesce(
                Sum(F("quantite") * F("prix_vente_unitaire")),
                Decimal("0.00")
            )
        )["total"]

        # Total déjà recouvré auprès des agents
        total_recouvre_agents = Recouvrement.objects.filter(
            agent__in=agents,
            superviseur=superviseur,
            date_recouvrement__gte=date_debut,
            date_recouvrement__lte=date_fin
        ).aggregate(
            total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
        )["total"]

        montant_a_recouvrer = max(
            total_ventes_agents - total_recouvre_agents,
            Decimal("0.00")
        )

        # =====================================================
        # 3️⃣ CASH DÉTENU PAR LE SUPERVISEUR (RÉEL)
        # =====================================================

        # a) Recouvrements agents encore en possession du superviseur
        recouvrements_non_remis = total_recouvre_agents

        # b) Ventes personnelles du superviseur
        ventes_superviseur = Vente.objects.filter(
            agent=superviseur,
            date_vente__gte=date_debut,
            date_vente__lte=date_fin,
            est_supprime=False
        ).aggregate(
            total=Coalesce(
                Sum(F("quantite") * F("prix_vente_unitaire")),
                Decimal("0.00")
            )
        )["total"]

        # c) Montant déjà remis au ROT
        montant_remis_rot = RecouvrementSuperviseur.objects.filter(
            superviseur=superviseur,
            date_recouvrement__gte=date_debut,
            date_recouvrement__lte=date_fin
        ).aggregate(
            total=Coalesce(Sum("montant"), Decimal("0.00"))
        )["total"]

        # d) Cash réellement détenu
        cash_detenu = max(
            (recouvrements_non_remis + ventes_superviseur) - montant_remis_rot,
            Decimal("0.00")
        )

        # =====================================================
        # 🔚 RÉSULTAT DASHBOARD
        # =====================================================
        return {
            "nombre_agents": nombre_agents,
            "montant_a_recouvrer": montant_a_recouvrer,
            "cash_detenu": cash_detenu,
            "montant_remis_rot": montant_remis_rot,
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
