
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

class SuperviseurAgentsService:

    @staticmethod
    def resolve_period(request):
        periode = request.GET.get("periode", "mois")
        today = timezone.now().date()

        if periode == "mois_prec":
            debut = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            fin = today.replace(day=1) - timedelta(days=1)

        elif periode == "custom":
            debut = request.GET.get("date_debut")
            fin = request.GET.get("date_fin")
            if debut and fin:
                debut = datetime.strptime(debut, "%Y-%m-%d").date()
                fin = datetime.strptime(fin, "%Y-%m-%d").date()
            else:
                debut = today.replace(day=1)
                fin = today

        else:  # mois courant
            debut = today.replace(day=1)
            fin = today

        return {
            "periode": periode,
            "date_debut": debut,
            "date_fin": fin,
        }

    @staticmethod
    def get_agents_ventes(superviseur, debut, fin):
        agents = Agent.objects.filter(
            superviseur=superviseur,
            est_actif=True
        ).exclude(type_agent='stagiaire')

        agents_data = []

        totals = {
            "ca": Decimal("0.00"),
            "quantite": Decimal("0.00"),
        }

        for agent in agents:
            ventes = Vente.objects.filter(
                agent=agent,
                date_vente__date__range=(debut, fin),
                est_supprime=False
            )

            ca = ventes.aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0.00")
                )
            )["total"]

            quantite = ventes.aggregate(
                total=Coalesce(Sum("quantite"), Decimal("0.00"))
            )["total"]

            recouvre = Recouvrement.objects.filter(
                agent=agent,
                superviseur=superviseur,
                date_recouvrement__date__range=(debut, fin)
            ).aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
            )["total"]

            reste = ca - recouvre

            derniere_vente = ventes.aggregate(
                last=Max("date_vente")
            )["last"]

            agents_data.append({
                "agent": agent,
                "ca": ca,
                "quantite": quantite,
                "recouvre": recouvre,
                "reste": reste,
                "derniere_vente": derniere_vente,
                "sans_vente_48h": (
                    derniere_vente is None or
                    derniere_vente < timezone.now() - timedelta(hours=72)
                )
            })

            totals["ca"] += ca
            totals["quantite"] += quantite

        return agents_data, totals

    @staticmethod
    def get_flux(superviseur, debut, fin):

        ca_expr = ExpressionWrapper(
            F("quantite") * F("prix_vente_unitaire"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        # 1️⃣ CA agents (même logique que ToutesLesVentesView)
        ventes_agents = Vente.objects.filter(
            agent__superviseur=superviseur,
            agent__type_agent__in=["terrain", "agent_gros"],
            date_vente__date__range=(debut, fin),
            est_supprime=False
        ).aggregate(
            total=Coalesce(Sum(ca_expr), Decimal("0.00"))
        )["total"]

        # 2️⃣ Recouvrements agents
        recouvre_agents = Recouvrement.objects.filter(
            superviseur=superviseur,
            date_recouvrement__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
        )["total"]

        # 3️⃣ À recouvrer
        reste_agents = ventes_agents - recouvre_agents

        # 4️⃣ CA superviseur (même règle)
        ventes_perso = Vente.objects.filter(
            agent=superviseur,
            date_vente__date__range=(debut, fin),
            est_supprime=False
        ).aggregate(
            total=Coalesce(Sum(ca_expr), Decimal("0.00"))
        )["total"]

        # 5️⃣ Remis au ROT
        remis_rot = RecouvrementSuperviseur.objects.filter(
            superviseur=superviseur,
            date_recouvrement__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(Sum("montant"), Decimal("0.00"))
        )["total"]

        # 6️⃣ Solde superviseur
        solde_superviseur = (recouvre_agents + ventes_perso) - remis_rot

        return {
            "ventes_agents": ventes_agents,
            "recouvre_agents": recouvre_agents,
            "reste_agents": reste_agents,
            "ventes_perso": ventes_perso,
            "remis_rot": remis_rot,
            "solde_superviseur": solde_superviseur,
        }


    @staticmethod
    def get_matrice_distribution(superviseur, debut, fin):
        distributions = DetailDistribution.objects.filter(
            distribution__superviseur=superviseur,
            distribution__agent_terrain__type_agent__in=["terrain", "agent_gros"],
            distribution__date_distribution__date__range=(debut, fin)
        ).values(
            "distribution__agent_terrain",
            "lot__produit__nom"
        ).annotate(
            quantite=Coalesce(Sum("quantite"), Decimal("0.00"))
        )

        agent_ids = {d["distribution__agent_terrain"] for d in distributions}
        agents = Agent.objects.in_bulk(agent_ids)

        lignes = {}
        produits = set()

        for d in distributions:
            agent_id = d["distribution__agent_terrain"]
            agent = agents.get(agent_id)
            if not agent:
                continue

            produits.add(d["lot__produit__nom"])

            lignes.setdefault(agent_id, {
                "agent": agent,   # objet Agent complet
                "produits": {}
            })

            lignes[agent_id]["produits"][d["lot__produit__nom"]] = d["quantite"]

        return {
            "lignes": lignes,      # dict par agent_id
            "colonnes": sorted(produits),
        }

    @staticmethod
    def build_kpis(totals, flux):
        ca_agents = flux["ventes_agents"]
        ca_superviseur = flux["ventes_perso"]
    
        return {
            # Activité
            "ca_total": ca_agents + ca_superviseur,
            "ca_agents": ca_agents,
            "ca_superviseur": ca_superviseur,
    
            # Risque terrain
            "reste_agents": flux["reste_agents"],
    
            # Discipline superviseur
            "solde_superviseur": flux["solde_superviseur"],
        }
    

