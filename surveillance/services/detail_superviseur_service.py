from collections import defaultdict
from decimal import Decimal
from collections import defaultdict


from core.models import Vente

from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService,
)

class DetailSuperviseurService:
    @staticmethod
    def get_data(superviseur):
        debut_actuel, fin_actuel = (
            ComparaisonPeriodeService.semaine_actuelle()
        )
        debut_prec, fin_prec = (
            ComparaisonPeriodeService.semaine_precedente()
        )
        ventes_actuelles = Vente.objects.filter(
            agent__superviseur=superviseur,
            est_supprime=False,
            date_vente__date__gte=debut_actuel,
            date_vente__date__lte=fin_actuel,
        ).select_related(
            "agent",
            "detail_distribution__lot__produit",
        )
        ventes_prec = Vente.objects.filter(
            agent__superviseur=superviseur,
            est_supprime=False,
            date_vente__date__gte=debut_prec,
            date_vente__date__lte=fin_prec,
        )
        kg_actuel = sum(
            vente.quantite_en_kg
            for vente in ventes_actuelles
        )
        kg_prec = sum(
            vente.quantite_en_kg
            for vente in ventes_prec
        )
        variation = (
            ComparaisonService.variation(
                kg_actuel,
                kg_prec
            )
        )
        # --------------------
        # Agents
        # --------------------
        agents = defaultdict(
            lambda: {
                "agent": None,
                "kg": 0,
                "produits": set(),
            }
        )

        for vente in ventes_actuelles:

            agent = vente.agent

            produit = (
                vente.detail_distribution
                .lot
                .produit
            )

            agents[agent.id]["agent"] = agent

            agents[agent.id]["kg"] += (
                vente.quantite_en_kg
            )

            agents[agent.id]["produits"].add(
                produit.id
            )

        agents_stats = []

        for item in agents.values():

            agents_stats.append({
                "agent": item["agent"],
                "kg": item["kg"],
                "nb_produits": len(
                    item["produits"]
                ),
            })

        agents_stats.sort(
            key=lambda x: x["kg"],
            reverse=True
        )

        # --------------------
        # Produits
        # --------------------

        produits = defaultdict(Decimal)

        for vente in ventes_actuelles:

            produit = (
                vente.detail_distribution
                .lot
                .produit
            )

            produits[produit] += (
                vente.quantite_en_kg
            )

        produits_stats = []

        for produit, kg in produits.items():

            produits_stats.append({
                "produit": produit,
                "kg": kg,
            })

        produits_stats.sort(
            key=lambda x: x["kg"],
            reverse=True
        )

        return {

            "superviseur": superviseur,
            "kg_actuel": round(kg_actuel,2),
            "kg_prec": round(kg_prec,2 ),
            "variation": round(variation,2),
            "agents_stats": agents_stats,
            "produits_stats": produits_stats,
        }