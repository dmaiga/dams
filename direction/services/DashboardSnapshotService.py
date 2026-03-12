from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense, DetailDistribution,
                         DistributionAgent)

from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Max, F, DecimalField,Q
from django.db.models import ExpressionWrapper, DecimalField

from decimal import Decimal

from core.models import Agent, Vente
from direction.services.dashboard_service import DashboardService


from django.core.cache import cache


class DashboardSnapshotService:

    @staticmethod
    def get_snapshot(periode_type, annee, mois, user):
        cache_key = f"dashboard:snapshot:{periode_type}:{annee}:{mois}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        snapshot = {}

        snapshot.update(
            DashboardService.get_kpis_globaux(periode_type, annee, mois)
        )
        snapshot["kpis_fournisseurs"] = DashboardService.get_kpis_fournisseurs(
            periode_type,
            annee,
            mois
        )


        snapshot["performances_agents"] = DashboardService.get_performances_agents(periode_type, annee, mois)
        snapshot.update(
            DashboardService.get_analyses_ventes_avancees(periode_type, annee, mois)
        )



        cache.set(cache_key, snapshot, 60 * 10)  # 10 minutes
        return snapshot
