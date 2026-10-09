"""Produits en possession des agents de vente (suivi du stock par le gestionnaire
de stock et le groupe « Suivi stock agents » ; vue d'un seul agent côté superviseur).

Même source de vérité que `direction/suivi-distributions/` (réutilise
`StockInvestigationService`) : un produit est « en possession » d'un agent tant
que `restant > 0` sur son `DetailDistribution`, et son ancienneté se compte depuis
la date de distribution (moment où le produit est remis à l'agent pour la vente).
Aucune distribution antérieure à `DATE_DEBUT_SUIVI_TERRAIN` n'est remontée.
"""

from django.utils import timezone

from direction.constants import (
    DATE_DEBUT_SUIVI_TERRAIN,
    SEUIL_ATTENTION_JOURS,
    SEUIL_CRITIQUE_JOURS,
)
from direction.services.stock_investigation_service import StockInvestigationService


class StockAgentsService:

    @staticmethod
    def produits_par_agent(*, superviseur=None, agent=None, produit_id=None):
        """Retourne une liste de blocs, un par agent détenant du stock (tous les agents
        si `superviseur` est omis, sinon ceux de ce superviseur) :

            {"agent": Agent, "recents": [ligne], "anciens": [ligne],
             "nb_recents": int, "nb_anciens": int}

        `recents` = distribués depuis moins de `SEUIL_ATTENTION_JOURS` jours,
        `anciens` = depuis `SEUIL_ATTENTION_JOURS` jours ou plus (à investiguer).
        Chaque ligne : produit_nom, quantite, date_distribution, jours, statut
        (`ok` | `attention` | `critique`). Triées de la plus ancienne à la plus récente.
        """
        details = (
            StockInvestigationService.base_queryset(DATE_DEBUT_SUIVI_TERRAIN)
            .filter(restant__gt=0, distribution__agent_terrain__isnull=False)
            .select_related(
                "distribution__agent_terrain__user",
                "distribution__agent_terrain__superviseur__user",
            )
            .order_by("distribution__date_distribution")
        )
        if superviseur is not None:
            details = details.filter(distribution__agent_terrain__superviseur=superviseur)
        if agent is not None:
            details = details.filter(distribution__agent_terrain=agent)
        if produit_id:
            details = details.filter(lot__produit_id=produit_id)

        maintenant = timezone.now()
        blocs = {}
        for d in details:
            agent_d = d.distribution.agent_terrain
            bloc = blocs.setdefault(
                agent_d.id,
                {"agent": agent_d, "recents": [], "anciens": []},
            )
            jours = (maintenant - d.distribution.date_distribution).days
            if jours >= SEUIL_CRITIQUE_JOURS:
                statut = "critique"
            elif jours >= SEUIL_ATTENTION_JOURS:
                statut = "attention"
            else:
                statut = "ok"
            ligne = {
                "produit_nom": d.lot.produit.nom,
                "quantite": d.restant,
                "date_distribution": d.distribution.date_distribution,
                "jours": jours,
                "statut": statut,
            }
            bloc["anciens" if jours >= SEUIL_ATTENTION_JOURS else "recents"].append(ligne)

        resultat = sorted(blocs.values(), key=lambda b: b["agent"].full_name or "")
        for bloc in resultat:
            bloc["nb_recents"] = len(bloc["recents"])
            bloc["nb_anciens"] = len(bloc["anciens"])
        return resultat
