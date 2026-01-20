from decimal import Decimal
from django.db.models import Sum, Max, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Agent, Vente, Recouvrement


class AgentTerrainListeService:
    """
    Service – Liste des agents (terrain & gros)
    Logique FACTUELLE (sans interprétation Direction)
    """

    @staticmethod
    def get_agents_liste(
        date_debut,
        date_fin,
        superviseur=None,
        type_agent=None,
    ):

        agents_qs = Agent.objects.filter(
            est_actif=True,
            type_agent__in=["terrain", "agent_gros"],
        ).select_related("superviseur", "user")

        if superviseur:
            agents_qs = agents_qs.filter(superviseur=superviseur)

        if type_agent:
            agents_qs = agents_qs.filter(type_agent=type_agent)

        now = timezone.now()
        agents_data = []

        # Conversion unité → kilo (lecture uniquement)
        kilo_expr = ExpressionWrapper(
            F("quantite") *
            Coalesce(
                F("detail_distribution__lot__produit__poids_unitaire_kg"),
                Decimal("1.0")
            ),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        for agent in agents_qs:
            ventes = Vente.objects.filter(
                agent=agent,
                date_vente__date__range=(date_debut, date_fin),
                est_supprime=False,
            )

            kilo_vendu = ventes.aggregate(
                total=Coalesce(Sum(kilo_expr), Decimal("0.00"))
            )["total"]

            total_ventes = ventes.aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0.00")
                )
            )["total"]

            recouvrements = Recouvrement.objects.filter(
                agent=agent,
                date_recouvrement__date__range=(date_debut, date_fin),
            ).aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
            )["total"]

            argent_en_possession = total_ventes - recouvrements

            derniere_vente = ventes.aggregate(
                last=Max("date_vente")
            )["last"]

            jours_inactif = (
                (now - derniere_vente).days
                if derniere_vente else None
            )

            agents_data.append({
                "agent": agent,
                "nom": agent.full_name,
                "telephone": agent.telephone,
                "type_agent": agent.get_type_agent_display(),
                "superviseur": agent.superviseur,

                # faits
                "kilo_vendu": kilo_vendu,
                "derniere_vente": derniere_vente,
                "jours_inactif": jours_inactif,
                "argent_en_possession": argent_en_possession,
            })

        return agents_data

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
