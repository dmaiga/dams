# services/vente_analyses.py
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum, F, Q, Case, When, IntegerField, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from core.models import Vente, Agent


class VenteAnalyseService:
    """Service d'analyse des ventes pour filtres, stats et top agents."""

    @staticmethod
    def normalize_period(periode, params):
        """Retourne date_debut, date_fin en fonction du type de période."""
        now = timezone.now()

        if periode == "annee":
            annee = int(params.get("annee", now.year))
            date_debut = timezone.make_aware(datetime(annee, 1, 1))
            date_fin = timezone.make_aware(datetime(annee, 12, 31, 23, 59, 59))

        elif periode == "mois":
            annee = int(params.get("annee", now.year))
            mois = int(params.get("mois", now.month))
            date_debut = timezone.make_aware(datetime(annee, mois, 1))
            if mois == 12:
                date_fin = timezone.make_aware(datetime(annee + 1, 1, 1)) - timedelta(seconds=1)
            else:
                date_fin = timezone.make_aware(datetime(annee, mois + 1, 1)) - timedelta(seconds=1)

        elif periode == "perso":
            d1 = params.get("date_debut")
            d2 = params.get("date_fin")
            if d1 and d2:
                date_debut = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
                date_fin = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d")) + timedelta(days=1, seconds=-1)
            else:
                # Valeurs par défaut si dates manquantes
                date_debut = timezone.make_aware(datetime(now.year, 1, 1))
                date_fin = now

        else:
            annee = now.year
            date_debut = timezone.make_aware(datetime(annee, 1, 1))
            date_fin = timezone.make_aware(datetime(annee, 12, 31, 23, 59, 59))

        return date_debut, date_fin

    # ----------------------------------------------------------------------
    @staticmethod
    def filter_ventes(date_debut, date_fin, agent_id=None, type_vente=None):
        """Retourne le queryset filtré selon période + filtres agent / type."""
        qs = Vente.objects.select_related(
            "agent",
            "client",
            "detail_distribution",
            "detail_distribution__lot",
            "detail_distribution__lot__produit",
        ).filter(
            date_vente__range=(date_debut, date_fin)
        ).order_by("-date_vente")

        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        if type_vente:
            qs = qs.filter(type_vente=type_vente)

        return qs

    # ----------------------------------------------------------------------
    @staticmethod
    def compute_stats(ventes_qs):
        """Calcule les stats globales des ventes filtrées."""
        # Calcul du CA
        ca_stats = ventes_qs.aggregate(
            total_ca=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0.00')),
            total_quantite=Coalesce(Sum('quantite'), Decimal('0.00')),
            ventes_gros=Sum(Case(When(type_vente="gros", then=1), default=0, output_field=IntegerField())),
            ventes_detail=Sum(Case(When(type_vente="detail", then=1), default=0, output_field=IntegerField())),
        )
        
        # Calcul de la marge (coût d'achat)
        # On calcule d'abord le coût total d'achat
        cout_stats = ventes_qs.aggregate(
            total_cout=Coalesce(
                Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')), 
                Decimal('0.00')
            )
        )
        
        total_ca = ca_stats["total_ca"] or Decimal("0.00")
        total_cout = cout_stats["total_cout"] or Decimal("0.00")
        total_marge = total_ca - total_cout
        
        # Calcul du taux de marge (éviter division par zéro)
        taux_marge = Decimal('0.00')
        if total_ca > 0:
            taux_marge = (total_marge / total_ca) * 100

        return {
            "total_ca": total_ca,
            "total_marge": total_marge,
            "taux_marge": taux_marge,
            "ventes_gros": ca_stats["ventes_gros"] or 0,
            "ventes_detail": ca_stats["ventes_detail"] or 0,
            "total_quantite": ca_stats["total_quantite"] or Decimal("0.00"),
            "clients_count": ventes_qs.values("client").distinct().count(),
            "agents_count": ventes_qs.values("agent").distinct().count(),
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def compute_top_agents(ventes_qs, limit=5):
        """Retourne le TOP agents par CA."""
        # Calcul du CA et de la marge par agent
        top_agents = (
            ventes_qs.values(
                "agent_id",
                "agent__user__first_name",
                "agent__user__last_name",
                "agent__type_agent"
            )
            .annotate(
                total_ca=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0.00')),
                total_cout=Coalesce(
                    Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')), 
                    Decimal('0.00')
                )
            )
            .annotate(
                total_marge=F('total_ca') - F('total_cout')
            )
            .order_by("-total_ca")[:limit]
        )
        
        # Formater les résultats
        formatted_agents = []
        for agent in top_agents:
            formatted_agents.append({
                'agent__user__first_name': agent['agent__user__first_name'],
                'agent__user__last_name': agent['agent__user__last_name'],
                'agent__type_agent': agent['agent__type_agent'],
                'total_ca': agent['total_ca'],
                'total_marge': agent['total_marge']
            })
        
        return formatted_agents

    # ----------------------------------------------------------------------
    @staticmethod
    def get_agents_list():
        """Liste des agents pour le filtre."""
        return Agent.objects.filter(
            type_agent__in=['terrain', 'entrepot', 'stagiaire']
        ).order_by("user__first_name")

    # ----------------------------------------------------------------------
    @staticmethod
    def get_ventes_avec_marge(ventes_qs):
        """Retourne les ventes avec marge calculée."""
        # On va calculer la marge dans la vue pour éviter les problèmes de requêtes complexes
        return ventes_qs