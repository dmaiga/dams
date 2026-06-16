from collections import defaultdict

from core.models import Vente

from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService,
)


class DetailProduitService:

    @staticmethod
    def get_data(produit):

        debut_actuel, fin_actuel = (
            ComparaisonPeriodeService.semaine_actuelle()
        )

        debut_prec, fin_prec = (
            ComparaisonPeriodeService.semaine_precedente()
        )

        ventes_actuelles = Vente.objects.filter(
            detail_distribution__lot__produit=produit,
            est_supprime=False,
            date_vente__date__gte=debut_actuel,
            date_vente__date__lte=fin_actuel,
        ).select_related(
            "agent",
            "agent__superviseur",
        )

        ventes_prec = Vente.objects.filter(
            detail_distribution__lot__produit=produit,
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

        superviseurs = defaultdict(
            lambda: {
                "superviseur": None,
                "kg": 0,
            }
        )

        agents = defaultdict(
            lambda: {
                "agent": None,
                "superviseur": None,
                "kg": 0,
            }
        )

        for vente in ventes_actuelles:

            superviseur = vente.agent.superviseur

            if superviseur:

                superviseurs[
                    superviseur.id
                ]["superviseur"] = superviseur

                superviseurs[
                    superviseur.id
                ]["kg"] += vente.quantite_en_kg

            agents[
                vente.agent.id
            ]["agent"] = vente.agent

            agents[
                vente.agent.id
            ]["superviseur"] = superviseur

            agents[
                vente.agent.id
            ]["kg"] += vente.quantite_en_kg

        superviseurs_stats = list(
            superviseurs.values()
        )

        superviseurs_stats.sort(
            key=lambda x: x["kg"],
            reverse=True
        )

        agents_stats = list(
            agents.values()
        )

        agents_stats.sort(
            key=lambda x: x["kg"],
            reverse=True
        )

        return {

            "produit": produit,

            "kg_actuel": round(
                kg_actuel,
                2
            ),

            "kg_prec": round(
                kg_prec,
                2
            ),

            "variation": round(
                variation,
                2
            ),

            "superviseurs_stats":
                superviseurs_stats,

            "agents_stats":
                agents_stats,
        }