# services/vente_analyses.py
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum, F, Q, Case, When, IntegerField, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from core.models import Vente, Agent
from datetime import datetime, time

class VenteAnalyseService:
 
    @staticmethod
    def filter_ventes(date_debut, date_fin, agent_id=None, type_vente=None, produit_id=None, lot_id=None  ):
        qs = (
            Vente.objects
            .select_related(
                "agent",
                "agent__user",
                "client",
                "stagiaire",
                "detail_distribution",
                "detail_distribution__lot",
                "detail_distribution__lot__produit",
            )
            .filter(date_vente__range=(date_debut, date_fin))
            .order_by("-date_vente")
        )

        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        if type_vente:
            qs = qs.filter(type_vente=type_vente)
        if produit_id:
            qs = qs.filter(detail_distribution__lot__produit_id=produit_id)
        if lot_id:
            qs = qs.filter(detail_distribution__lot_id=lot_id)
        
        return qs

    # ------------------------------------------------------------------
    # STATS GLOBALES — 1 SEULE PASSE SQL
    # ------------------------------------------------------------------
    @staticmethod
    def compute_stats(ventes_qs):
        stats = ventes_qs.aggregate(
            total_ca=Coalesce(
                Sum(F("quantite") * F("prix_vente_unitaire")),
                Decimal("0.00")
            ),
            total_cout=Coalesce(
                Sum(F("quantite") * F("detail_distribution__lot__prix_achat_unitaire")),
                Decimal("0.00")
            ),
            total_quantite=Coalesce(Sum("quantite"), Decimal("0.00")),
            ventes_gros=Sum(
                Case(When(type_vente="gros", then=1), default=0, output_field=IntegerField())
            ),
            ventes_detail=Sum(
                Case(When(type_vente="detail", then=1), default=0, output_field=IntegerField())
            ),
        )

        total_ca = stats["total_ca"]
        total_cout = stats["total_cout"]
        total_marge = total_ca - total_cout if total_ca else Decimal("0.00")
        taux_marge = (total_marge / total_ca * 100) if total_ca else Decimal("0.00")

        return {
            "total_ca": total_ca,
            "total_marge": total_marge,
            "taux_marge": taux_marge,
            "ventes_gros": stats["ventes_gros"] or 0,
            "ventes_detail": stats["ventes_detail"] or 0,
            "total_quantite": stats["total_quantite"],
            "clients_count": ventes_qs.values("client_id").distinct().count(),
            "agents_count": ventes_qs.values("agent_id").distinct().count(),
        }

    # ------------------------------------------------------------------
    # TOP AGENTS — PAS DE BOUCLE DB
    # ------------------------------------------------------------------
    @staticmethod
    def compute_top_agents(ventes_qs, limit=5):
        return (
            ventes_qs
            .values(
                "agent_id",
                "agent__user__first_name",
                "agent__user__last_name",
                "agent__type_agent",
            )
            .annotate(
                total_ca=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0.00")
                ),
                total_cout=Coalesce(
                    Sum(F("quantite") * F("detail_distribution__lot__prix_achat_unitaire")),
                    Decimal("0.00")
                ),
            )
            .annotate(total_marge=F("total_ca") - F("total_cout"))
            .order_by("-total_ca")[:limit]
        )

    # ------------------------------------------------------------------
    @staticmethod
    def get_agents_list():
        return Agent.objects.filter(
            type_agent__in=["terrain", "entrepot", "stagiaire"],
            est_actif=True

        ).select_related("user").order_by("user__first_name")

    # ------------------------------------------------------------------
    @staticmethod
    def normalize_period(periode, params):
        now = timezone.now()

        if periode == "annee":
            annee = int(params.get("annee", now.year))
            return (
                timezone.make_aware(datetime(annee, 1, 1)),
                timezone.make_aware(datetime(annee, 12, 31, 23, 59, 59)),
            )

        if periode == "mois":
            annee = int(params.get("annee", now.year))
            mois = int(params.get("mois", now.month))
            debut = timezone.make_aware(datetime(annee, mois, 1))
            fin = (
                timezone.make_aware(datetime(annee + 1, 1, 1))
                if mois == 12
                else timezone.make_aware(datetime(annee, mois + 1, 1))
            ) - timedelta(seconds=1)
            return debut, fin
        
        # -------------------------------------------------
        # PERIODE PERSONNALISÉE
        # -------------------------------------------------
        if periode == "perso":
            date_debut = params.get("date_debut")
            date_fin = params.get("date_fin")
        
            if date_debut and date_fin:
                debut = timezone.make_aware(
                    datetime.combine(
                        datetime.fromisoformat(date_debut).date(),
                        time.min
                    )
                )
        
                fin = timezone.make_aware(
                    datetime.combine(
                        datetime.fromisoformat(date_fin).date(),
                        time.max
                    )
                )
        
                return debut, fin
        
        # fallback sécurité
        return (
            timezone.make_aware(datetime(now.year, 1, 1)),
            now,
        )
      

    """Service d'analyse des ventes pour filtres, stats et top agents."""
    
    @staticmethod
    def get_agents_inactifs(depuis_jours=3):
        """Retourne la liste des agents qui n'ont pas fait de ventes depuis X jours."""
        seuil = timezone.now() - timedelta(days=depuis_jours)
    
        agents = Agent.objects.filter(type_agent__in=["terrain", "entrepot"])
        agents_inactifs = []
    
        for agent in agents:
            # Dernière vente
            derniere_vente = (
                Vente.objects.filter(agent=agent)
                .order_by('-date_vente')
                .first()
            )
    
            if derniere_vente:
                if derniere_vente.date_vente < seuil:
                    agents_inactifs.append({
                        "nom": agent.full_name,
                        "jours_depuis": (timezone.now() - derniere_vente.date_vente).days,
                        "derniere_vente": derniere_vente.date_vente,
                    })
            else:
                # Aucun historique de vente
                agents_inactifs.append({
                    "nom": agent.full_name,
                    "jours_depuis": None,
                    "derniere_vente": None,
                })
    
        # Trier : ceux sans ventes d'abord, puis les plus anciens
        agents_inactifs.sort(key=lambda x: (x["jours_depuis"] is not None, x["jours_depuis"]))
        return agents_inactifs
    

    # ----------------------------------------------------------------------
    @staticmethod
    def get_ventes_avec_marge(ventes_qs):
        """Retourne les ventes avec marge calculée."""
        # On va calculer la marge dans la vue pour éviter les problèmes de requêtes complexes
        return ventes_qs
    
    # ----------------------------------------------------------------------
   