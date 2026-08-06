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
)
from finance.services import solde_superviseur, synchroniser_engagements_champ

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
    # AGENTS TERRAIN
    # =====================================================
    @staticmethod
    def get_agents(superviseur):
        return Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=['terrain', 'agent_gros','stagiaire','agent_polivalent'],
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
        - montant_a_recouvrer : argent encore chez les agents (fenêtre mois courant)
        - cash_detenu / montant_remis_rot : source de vérité unique = finance.services.
        solde_superviseur (décisions n°13/14/15, sprint-03) — ne pas recalculer
        localement, pour éviter la divergence avec le dashboard finance direction.
        """

        # 🔹 Références temporelles
        date_debut, date_fin = get_periode_courante()
        date_ref = get_date_operationnelle(superviseur)

        # =====================================================
        # 1️⃣ AGENTS ACTIFS DU SUPERVISEUR
        # =====================================================
        agents = Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=["terrain", "agent_gros","agent_polivalent","stagiaire"],
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
        # 3️⃣ SOLDE RÉEL DU SUPERVISEUR (finance.services, source de vérité)
        # =====================================================
        solde = solde_superviseur(superviseur)

        # =====================================================
        # 🔚 RÉSULTAT DASHBOARD
        # =====================================================
        return {
            "nombre_agents": nombre_agents,
            "montant_a_recouvrer": montant_a_recouvrer,
            "cash_detenu": solde["solde"],
            "montant_remis_rot": solde["deja_remis"],
            "remboursements_champ": solde["remboursements_champ"],
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
    # BUILD DASHBOARD
    # =====================================================
    @staticmethod
    def build_dashboard_perimetre(user):
        superviseur = SuperviseurDashboardService.get_superviseur(user)
        if not superviseur:
            return None

        # Synchronisation engagements champ (sprint-06, Constat 1, étendue
        # 06/08/2026) : le KPI "Cash détenu" ci-dessous (get_finances_superviseur
        # → finance.services.solde_superviseur) intègre remboursements_champ —
        # un remboursement fait côté dams_agro et pas encore appris par `dams`
        # fausserait ce chiffre, visible en premier sur ce dashboard (avant même
        # que le superviseur aille sur finance:mes_engagements_champ). Best-effort
        # et court-circuitée s'il n'y a rien d'ouvert à vérifier (voir docstring
        # de synchroniser_engagements_champ) — coût réseau nul dans le cas courant.
        synchroniser_engagements_champ(superviseur)

        return {
            'superviseur': superviseur,

            # Agents
            'agents_terrain': SuperviseurDashboardService.get_agents(superviseur),

            # Finances (post-clôture)
            'finances_superviseur': SuperviseurDashboardService.get_finances_superviseur(superviseur),

            # Détail agents
            'agents_financiers': SuperviseurDashboardService.get_agents_financiers(superviseur),
        }
