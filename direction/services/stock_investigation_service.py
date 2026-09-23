# services/stock_investigation_service.py
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Max, Min, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import DetailDistribution, Vente
from direction.constants import SEUIL_ATTENTION_JOURS, SEUIL_CRITIQUE_JOURS


class StockInvestigationService:
    """Base commune à direction.suivi_distributions : traçabilité des produits
    distribués (table 1) et liste des produits en circulation sans vente
    depuis plus de SEUIL_ATTENTION_JOURS jours, à remettre à un superviseur/
    agent pour investigation terrain (table 2, sprint-14, 17/09/2026)."""

    # ------------------------------------------------------------------
    # QUERYSET DE BASE — annotations partagées par les deux tableaux
    # ------------------------------------------------------------------

    @staticmethod
    def base_queryset(date_debut_suivi):
        return (
            DetailDistribution.objects
            .filter(distribution__date_distribution__date__gte=date_debut_suivi)
            .select_related(
                "lot",
                "lot__produit",
                "lot__fournisseur",
                "distribution",
                "distribution__superviseur",
                "distribution__agent_terrain",
            )
            .annotate(
                total_vendu=Coalesce(
                    Sum("vente__quantite", filter=Q(vente__est_supprime=False)),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
            .annotate(
                restant=ExpressionWrapper(
                    F("quantite") - F("total_vendu"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
            .annotate(
                valeur_immobilisee=ExpressionWrapper(
                    F("restant") * F("lot__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            # Corrélation réception → distribution → vente (sprint suivi-distributions,
            # 23/09/2026) : sans ces deux dates, un produit soldé ne montre plus que sa
            # date de distribution — impossible de vérifier depuis cette page si la vente
            # est arrivée vite ou tardivement, ni quand elle a été réellement saisie.
            .annotate(
                date_premiere_vente=Min(
                    "vente__date_vente", filter=Q(vente__est_supprime=False)
                ),
                date_derniere_vente=Max(
                    "vente__date_vente", filter=Q(vente__est_supprime=False)
                ),
                date_enregistrement_derniere_vente=Max(
                    "vente__date_creation", filter=Q(vente__est_supprime=False)
                ),
            )
            .prefetch_related(
                Prefetch(
                    "vente_set",
                    queryset=Vente.objects.filter(est_supprime=False).order_by("date_vente"),
                    to_attr="ventes_actives",
                )
            )
        )

    # ------------------------------------------------------------------
    # FILTRES COMMUNS (superviseur/agent/produit/période) — partagés par les
    # deux tableaux et par les exports.
    # ------------------------------------------------------------------

    @staticmethod
    def filtrer(details, superviseur_id=None, agent_id=None, produit_id=None,
                date_debut=None, date_fin=None):
        if superviseur_id:
            details = details.filter(distribution__superviseur_id=superviseur_id)
        if agent_id:
            details = details.filter(distribution__agent_terrain_id=agent_id)
        if produit_id:
            details = details.filter(lot__produit_id=produit_id)
        if date_debut:
            details = details.filter(distribution__date_distribution__date__gte=date_debut)
        if date_fin:
            details = details.filter(distribution__date_distribution__date__lte=date_fin)
        return details

    # ------------------------------------------------------------------
    # TABLE 2 — produits en circulation depuis plus de SEUIL_ATTENTION_JOURS
    # jours (décision mdmaiga 17/09/2026 : tous les produits > 7 jours, pas
    # seulement les cas critiques ≥ 14 jours — la liste doit capter le
    # problème tôt).
    # ------------------------------------------------------------------

    @staticmethod
    def a_investiguer(details):
        seuil_date = timezone.now() - timezone.timedelta(days=SEUIL_ATTENTION_JOURS)
        return (
            details
            .filter(
                restant__gt=0,
                distribution__date_distribution__lte=seuil_date,
                # Un superviseur inactif (parti/désactivé) n'est plus un
                # destinataire valable de la checklist terrain — décision
                # mdmaiga, cohérent avec le filtre déjà appliqué au select
                # "superviseur" du formulaire (Agent.objects.filter(est_actif=True)).
                distribution__superviseur__est_actif=True,
            )
            .order_by("distribution__date_distribution")
        )

    # ------------------------------------------------------------------
    # STATUT DE COULEUR — calculé en Python (volume par page toujours
    # faible : pagination à 20, ou liste d'investigation ciblée), pas en SQL.
    # ------------------------------------------------------------------

    @staticmethod
    def annoter_statut(lignes):
        now = timezone.now()
        for d in lignes:
            if d.restant > 0:
                jours = (now - d.distribution.date_distribution).days
                d.jours_ecoules = jours
                if jours >= SEUIL_CRITIQUE_JOURS:
                    d.statut_circulation = "critique"
                elif jours >= SEUIL_ATTENTION_JOURS:
                    d.statut_circulation = "attention"
                else:
                    d.statut_circulation = "ok"
            else:
                d.jours_ecoules = None
                d.statut_circulation = None

            # Étalement de la vente dans le temps : un produit peut être écoulé en
            # plusieurs fois sur plusieurs jours plutôt qu'en une seule vente — sans
            # ça, "vendu le X" n'affiche que la dernière date et masque l'étalement
            # réel (utile pour repérer un écoulement anormalement lent).
            if d.date_premiere_vente and d.date_derniere_vente:
                d.etalement_vente_jours = (d.date_derniere_vente - d.date_premiere_vente).days
            else:
                d.etalement_vente_jours = None
        return lignes

    # ------------------------------------------------------------------
    # REGROUPEMENT SUPERVISEUR → AGENT → PRODUITS (sprint-14, révision
    # 17/09/2026) : la liste d'investigation n'est pas un document comptable
    # (pas de fournisseur, pas de valorisation) mais une checklist terrain —
    # un agent de vérification la parcourt superviseur par superviseur, puis
    # agent par agent, pour confirmer la présence physique des produits.
    # `lignes` doit déjà être passé par `annoter_statut`.
    # ------------------------------------------------------------------

    @staticmethod
    def regrouper_par_superviseur(lignes):
        groupes = {}
        for d in lignes:
            superviseur = d.distribution.superviseur
            agent = d.distribution.agent_terrain
            cle_sup = superviseur.id if superviseur else None
            groupe = groupes.setdefault(
                cle_sup, {"superviseur": superviseur, "agents": {}}
            )
            bloc_agent = groupe["agents"].setdefault(
                agent.id, {"agent": agent, "produits": []}
            )
            bloc_agent["produits"].append({
                "produit_nom": d.lot.produit.nom,
                "quantite": d.restant,
                "date_reference": d.distribution.date_distribution,
                "jours_ecoules": d.jours_ecoules,
                "statut_circulation": d.statut_circulation,
            })

        resultat = []
        for groupe in groupes.values():
            agents = list(groupe["agents"].values())
            for bloc_agent in agents:
                bloc_agent["produits"].sort(key=lambda p: p["date_reference"])
                bloc_agent["nb_produits"] = len(bloc_agent["produits"])
            agents.sort(key=lambda a: a["agent"].full_name or "")
            resultat.append({
                "superviseur": groupe["superviseur"],
                "agents": agents,
                "nb_agents": len(agents),
            })
        resultat.sort(
            key=lambda g: g["superviseur"].full_name if g["superviseur"] else ""
        )
        return resultat
