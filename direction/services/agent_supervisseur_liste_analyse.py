#/core/services/
from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense, DetailDistribution,
                         DistributionAgent,RecouvrementSuperviseur)

from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Max, F, DecimalField,Q
from django.db.models import ExpressionWrapper, DecimalField

from decimal import Decimal

from core.models import Agent, Vente

from django.db.models.functions import Coalesce

from django.core.cache import cache

class SuperviseurAnalysisService:

    @staticmethod
    def get_superviseurs_finance_mensuel():
        today = timezone.now().date()
        debut_mois = today.replace(day=1)
    
        data = []
    
        superviseurs = Agent.objects.filter(type_agent='entrepot', est_actif=True)
    
        for sup in superviseurs:
        
            # 1️⃣ Ventes personnelles du superviseur
            ventes_perso = Vente.objects.filter(
                agent=sup,
                date_vente__date__gte=debut_mois,
                est_supprime=False
            ).aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0")
                )
            )["total"]
    
            # 2️⃣ Ventes réalisées par les agents
            ventes_agents = Vente.objects.filter(
                agent__superviseur=sup,
                agent__type_agent__in=["terrain", "agent_gros"],
                date_vente__date__gte=debut_mois,
                est_supprime=False
            ).aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0")
                )
            )["total"]
    
            # 3️⃣ Recouvrements effectués auprès des agents
            recouvre_agents = Recouvrement.objects.filter(
                superviseur=sup,
                date_recouvrement__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0"))
            )["total"]
    
            # 4️⃣ Montant encore chez les agents (À RECOUVRER)
            montant_chez_agents = ventes_agents - recouvre_agents
    
            # 5️⃣ Montants remis au ROT
            remis_rot = RecouvrementSuperviseur.objects.filter(
                superviseur=sup,
                date_creation__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]
    
            # 6️⃣ Solde réel détenu par le superviseur
            solde_superviseur = (ventes_perso + recouvre_agents) - remis_rot
    
            data.append({
                "superviseur": sup,
                "ventes_perso": ventes_perso,
                "recouvre_agents": recouvre_agents,
                "montant_chez_agents": montant_chez_agents,
                "remis_rot": remis_rot,
                "solde_superviseur": solde_superviseur,
            })
    
        return data

    @staticmethod
    def get_rots_finance_mensuel():
        today = timezone.now().date()
        debut_mois = today.replace(day=1)
        fin_mois = today
    
        data = []
    
        rots = Agent.objects.filter(type_agent='rot', est_actif=True)
    
        for rot in rots:
            recu_superviseurs = RecouvrementSuperviseur.objects.filter(
                rot=rot,
                date_creation__date__range=(debut_mois, fin_mois)
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]
    
            verse_banque = VersementBancaire.objects.filter(
                effectue_par=rot,
                date_versement_reelle__date__range=(debut_mois, fin_mois)
            ).aggregate(
                total=Coalesce(Sum("montant_vente"), Decimal("0"))
            )["total"]
    
            depenses = Depense.objects.filter(
                effectue_par=rot,
                date_depense__date__range=(debut_mois, fin_mois)
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]
    
            data.append({
                "rot": rot,
                "recouvre": recu_superviseurs,
                "verse_banque": verse_banque,
                "depenses": depenses,
                "solde": recu_superviseurs - verse_banque - depenses,
            })
    
        return data
    