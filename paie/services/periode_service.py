from decimal import Decimal
from django.db.models import Sum, Max, F, DecimalField, ExpressionWrapper, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Agent, Vente, Recouvrement
from django.db.models import Value

class PeriodePaieService:

    @staticmethod
    def resolve(request):
        periode = request.GET.get("periode", "mensuel")
        today = timezone.now().date()

        if periode == "hebdo":
            debut = today - timedelta(days=today.weekday())
            fin = debut + timedelta(days=6)

        elif periode == "mensuel":
            debut = today.replace(day=1)
            fin = today

        elif periode == "custom":
            debut = datetime.strptime(
                request.GET.get("date_debut"), "%Y-%m-%d"
            ).date()
            fin = datetime.strptime(
                request.GET.get("date_fin"), "%Y-%m-%d"
            ).date()
        else:
            raise ValueError("Période invalide")

        return {
            "periode": periode,
            "date_debut": debut,
            "date_fin": fin,
        }
