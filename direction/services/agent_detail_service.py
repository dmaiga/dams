from decimal import Decimal
from django.db.models import Sum, Max, F, DecimalField, ExpressionWrapper, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Agent, Vente, Recouvrement
from django.db.models import Value

class AgentDetailService:
    """
    Service – Détail d’un agent (terrain / gros)
    Logique factuelle + indicateurs visuels simples
    """

    @staticmethod
    def get_agent_detail(agent, date_debut, date_fin):
        now = timezone.now()
    
        ventes = Vente.objects.filter(
            agent=agent,
            date_vente__date__range=(date_debut, date_fin),
            est_supprime=False,
        ).annotate(
            kilo_ligne=ExpressionWrapper(
                F("quantite") *
                Coalesce(
                    F("detail_distribution__lot__produit__poids_unitaire_kg"),
                    Value(1)
                ),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            ca_ligne=ExpressionWrapper(
                F("quantite") * F("prix_vente_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            marge_ligne=ExpressionWrapper(
                (F("quantite") * F("prix_vente_unitaire")) -
                (F("quantite") * F("detail_distribution__lot__prix_achat_unitaire")),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
    
        total_kg = ventes.aggregate(
            total=Coalesce(Sum("kilo_ligne"), Decimal("0.00"))
        )["total"]
    
        total_ca = ventes.aggregate(
            total=Coalesce(Sum("ca_ligne"), Decimal("0.00"))
        )["total"]
    
        total_marge = ventes.aggregate(
            total=Coalesce(Sum("marge_ligne"), Decimal("0.00"))
        )["total"]
    
        recouvrements = Recouvrement.objects.filter(
            agent=agent,
            date_recouvrement__date__range=(date_debut, date_fin),
        ).aggregate(
            total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
        )["total"]
    
        argent_en_possession = total_ca - recouvrements
    
        derniere_vente = ventes.aggregate(
            last=Max("date_vente")
        )["last"]
    
        jours_inactif = (now - derniere_vente).days if derniere_vente else None
    
        nb_jours = max((date_fin - date_debut).days, 1)
        kg_par_jour = total_kg / nb_jours
    
        couleur = (
            "success" if kg_par_jour >= Decimal("50")
            else "warning" if kg_par_jour >= Decimal("20")
            else "error"
        )
    
        ventes_par_produit = (
            ventes
            .values("detail_distribution__lot__produit__nom")
            .annotate(
                quantite=Coalesce(Sum("quantite"), Decimal("0.00")),
                kilo=Coalesce(Sum("kilo_ligne"), Decimal("0.00")),
                ca=Coalesce(Sum("ca_ligne"), Decimal("0.00")),
                marge=Coalesce(Sum("marge_ligne"), Decimal("0.00")),
            )
            .order_by("-kilo")
        )
        # Infos opérationnelles
        marche = agent.marche_affectation
        superviseur = agent.superviseur
        type_agent = agent.type_agent

    
        return {
            # Identité
            "agent": agent,
            "marche": marche,
            "superviseur": superviseur,
            "type_agent": type_agent,
        
            # Activité
            "total_kg": total_kg,
            "kg_par_jour": kg_par_jour,
            "ca_total": total_ca,
            "marge_totale": total_marge,
            "argent_en_possession": argent_en_possession,
        
            # Suivi terrain
            "derniere_vente": derniere_vente,
            "jours_inactif": jours_inactif,
            "couleur_performance": couleur,
        
            # Détail
            "ventes_par_produit": ventes_par_produit,
        }
        

    @staticmethod
    def resolve_period(request):
        periode = request.GET.get("periode", "hebdo")
        today = timezone.now().date()

        if periode == "hebdo":
            # Lundi → aujourd’hui
            debut = today - timedelta(days=today.weekday())
            fin = today

        elif periode == "mensuel":
            debut = today.replace(day=1)
            fin = today

        elif periode == "custom":
            debut_str = request.GET.get("date_debut")
            fin_str = request.GET.get("date_fin")

            if debut_str and fin_str:
                debut = datetime.strptime(debut_str, "%Y-%m-%d").date()
                fin = datetime.strptime(fin_str, "%Y-%m-%d").date()
            else:
                # fallback hebdo
                debut = today - timedelta(days=today.weekday())
                fin = today
                periode = "hebdo"

        else:
            # sécurité
            debut = today - timedelta(days=today.weekday())
            fin = today
            periode = "hebdo"

        return {
            "periode": periode,
            "date_debut": debut,
            "date_fin": fin,
        }
