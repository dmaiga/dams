from datetime import datetime
from decimal import Decimal

from django.db.models import F, Max, Q, Sum
from django.utils import timezone

from core.models import Agent, AffectationLotSuperviseur, DetailDistribution, LotEntrepot
from surveillance.constants import (
    DATE_PLANCHER_STOCK,
    DELAI_ACTIVITE_COMMERCIALE_JOURS,
    DELAI_RETENTION_ACTEURS_JOURS,
    DELAI_STOCK_DORMANT_JOURS,
)

# Agents dont l'activité commerciale/la rétention de stock est surveillée —
# les Mamis (terrain) et les agents en gros. Ni les superviseurs (rôle
# distinct, cf. rétention "superviseur"), ni les stagiaires/polyvalents, non
# mentionnés dans la demande métier.
TYPES_AGENT_VENTE = ['terrain', 'agent_gros']


class StockAgeService:
    @staticmethod
    def _seuil_activite():
        return timezone.now() - timezone.timedelta(days=DELAI_ACTIVITE_COMMERCIALE_JOURS)

    @staticmethod
    def _seuil_dormant_entrepot():
        return timezone.now() - timezone.timedelta(days=DELAI_STOCK_DORMANT_JOURS)

    @staticmethod
    def _seuil_retention_acteurs():
        return timezone.now() - timezone.timedelta(days=DELAI_RETENTION_ACTEURS_JOURS)

    # ------------------------------------------------------------------
    # Alerte 1 — activité commerciale : dernière vente VALIDE de l'agent,
    # tous lots/distributions confondus. Décorrélée du stock/lot — la
    # question posée est uniquement "quand cet agent a-t-il vendu pour la
    # dernière fois ?", jamais "quand a-t-il vendu CE lot ?" (docs/sprints/
    # Correctif du 2026-08-13 : l'ancien calcul, par DetailDistribution,
    # pouvait déclarer un agent inactif à cause d'un vieux lot alors qu'il
    # avait vendu récemment sur un lot plus récent).
    # ------------------------------------------------------------------

    @staticmethod
    def _queryset_agents_sans_vente_recente(seuil):
        return (
            Agent.objects
            .filter(
                type_agent__in=TYPES_AGENT_VENTE,
                est_actif=True,
                # Agent réellement entré en activité sur la fenêtre fiable —
                # simple garde-fou de population, pas un critère de calcul :
                # la dernière vente elle-même n'est jamais filtrée par lot.
                distributions_recues__date_distribution__date__gte=DATE_PLANCHER_STOCK,
            )
            .annotate(
                derniere_vente=Max('vente__date_vente', filter=Q(vente__est_supprime=False))
            )
            .filter(Q(derniere_vente__isnull=True) | Q(derniere_vente__lte=seuil))
        )

    @staticmethod
    def agents_sans_vente_recente(limit=None):
        seuil = StockAgeService._seuil_activite()
        now = timezone.now()

        qs = (
            StockAgeService._queryset_agents_sans_vente_recente(seuil)
            .select_related('superviseur')
            .order_by('derniere_vente')
        )
        if limit is not None:
            qs = qs[:limit]

        return [
            {
                "agent": agent,
                "superviseur": agent.superviseur,
                "derniere_vente": agent.derniere_vente,
                "jours_ecoules": (now - agent.derniere_vente).days if agent.derniere_vente else None,
            }
            for agent in qs
        ]

    @staticmethod
    def count_agents_sans_vente_recente():
        seuil = StockAgeService._seuil_activite()
        return StockAgeService._queryset_agents_sans_vente_recente(seuil).count()

    # ------------------------------------------------------------------
    # Alerte 2 — stock ancien : depuis combien de temps un produit est-il
    # détenu sans être écoulé ? Trois emplacements distincts, chacun avec
    # son propre seuil (refonte du 2026-08-13) :
    #   - "entrepot"    : LotEntrepot encore au dépôt central (15 jours) ;
    #   - "superviseur" : AffectationLotSuperviseur pas encore redistribuée
    #                     à un agent terrain (3 jours) ;
    #   - "agent"       : DetailDistribution détenu par un agent de vente,
    #                     pas encore totalement vendu (3 jours).
    # ------------------------------------------------------------------

    @staticmethod
    def _queryset_lots_dormants_entrepot(seuil):
        return LotEntrepot.objects.filter(
            quantite_restante__gt=0,
            date_reception__lte=seuil,
            date_reception__date__gte=DATE_PLANCHER_STOCK,
        )

    @staticmethod
    def _queryset_lots_dormants_superviseur(seuil_date):
        return AffectationLotSuperviseur.objects.filter(
            quantite_restante__gt=0,
            date_affectation__lte=seuil_date,
            date_affectation__gte=DATE_PLANCHER_STOCK,
        )

    @staticmethod
    def _queryset_stock_retenu_agents(seuil):
        return (
            DetailDistribution.objects
            .filter(
                distribution__agent_terrain__type_agent__in=TYPES_AGENT_VENTE,
                distribution__date_distribution__lte=seuil,
                distribution__date_distribution__date__gte=DATE_PLANCHER_STOCK,
            )
            .select_related(
                'distribution__agent_terrain', 'distribution__agent_terrain__superviseur',
                'lot__produit', 'lot__fournisseur',
            )
        )

    @staticmethod
    def _lignes_stock_retenu_agents(seuil, limit=None):
        """Filtre côté Python sur quantite_restante_calculee (property du modèle,
        seule source de vérité pour "combien reste-t-il sur ce détail" — déjà
        utilisée ailleurs, cf. core/models.py). Volume attendu faible (détails
        de distribution âgés de plus de quelques jours), le N+1 induit est
        accepté au même titre que agents/services/agent_stock_service.py."""
        now = timezone.now()
        lignes = []
        for detail in StockAgeService._queryset_stock_retenu_agents(seuil).order_by('distribution__date_distribution'):
            quantite_restante = detail.quantite_restante_calculee
            if quantite_restante <= 0:
                continue

            agent = detail.distribution.agent_terrain
            lot = detail.lot
            date_reference = detail.distribution.date_distribution

            lignes.append({
                "origine": "agent",
                "id": detail.id,
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "reference_lot": lot.reference_lot,
                "localisation": agent.full_name,
                "agent": agent,
                "superviseur": agent.superviseur,
                "date_reference": date_reference,
                "date_tri": date_reference.date() if isinstance(date_reference, datetime) else date_reference,
                "quantite_restante": quantite_restante,
                "valeur_immobilisee": quantite_restante * lot.prix_achat_unitaire,
                "jours_ecoules": (now - date_reference).days,
            })
            if limit is not None and len(lignes) >= limit:
                break
        return lignes

    @staticmethod
    def lots_stock_dormant(limit=None):
        seuil_entrepot = StockAgeService._seuil_dormant_entrepot()
        seuil_retention = StockAgeService._seuil_retention_acteurs()
        now = timezone.now()

        lots = (
            StockAgeService._queryset_lots_dormants_entrepot(seuil_entrepot)
            .select_related('produit', 'fournisseur')
            .order_by('date_reception')
        )
        affectations = (
            StockAgeService._queryset_lots_dormants_superviseur(seuil_retention.date())
            .select_related('lot__produit', 'lot__fournisseur', 'superviseur')
            .order_by('date_affectation')
        )
        if limit is not None:
            lots = lots[:limit]
            affectations = affectations[:limit]

        lignes = []
        for lot in lots:
            lignes.append({
                "origine": "entrepot",
                "id": lot.id,
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "reference_lot": lot.reference_lot,
                "localisation": "Entrepôt central",
                "superviseur": None,
                "date_reference": lot.date_reception,
                "date_tri": lot.date_reception.date() if isinstance(lot.date_reception, datetime) else lot.date_reception,
                "quantite_restante": lot.quantite_restante,
                "valeur_immobilisee": lot.quantite_restante * lot.prix_achat_unitaire,
                "jours_ecoules": (now - lot.date_reception).days,
            })

        for affectation in affectations:
            lot = affectation.lot
            lignes.append({
                "origine": "superviseur",
                "id": affectation.id,
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "reference_lot": lot.reference_lot,
                "localisation": affectation.superviseur.full_name,
                "superviseur": affectation.superviseur,
                "date_reference": affectation.date_affectation,
                "date_tri": affectation.date_affectation,
                "quantite_restante": affectation.quantite_restante,
                "valeur_immobilisee": affectation.quantite_restante * lot.prix_achat_unitaire,
                "jours_ecoules": (now.date() - affectation.date_affectation).days,
            })

        lignes.extend(StockAgeService._lignes_stock_retenu_agents(seuil_retention, limit=limit))

        lignes.sort(key=lambda item: item["date_tri"])
        if limit is not None:
            lignes = lignes[:limit]
        return lignes

    @staticmethod
    def count_lots_stock_dormant():
        seuil_entrepot = StockAgeService._seuil_dormant_entrepot()
        seuil_retention = StockAgeService._seuil_retention_acteurs()
        return (
            StockAgeService._queryset_lots_dormants_entrepot(seuil_entrepot).count()
            + StockAgeService._queryset_lots_dormants_superviseur(seuil_retention.date()).count()
            + len(StockAgeService._lignes_stock_retenu_agents(seuil_retention))
        )

    @staticmethod
    def valeur_stock_dormant():
        seuil_entrepot = StockAgeService._seuil_dormant_entrepot()
        seuil_retention = StockAgeService._seuil_retention_acteurs()

        total_entrepot = (
            StockAgeService._queryset_lots_dormants_entrepot(seuil_entrepot)
            .aggregate(total=Sum(F('quantite_restante') * F('prix_achat_unitaire')))['total']
            or 0
        )
        total_superviseur = (
            StockAgeService._queryset_lots_dormants_superviseur(seuil_retention.date())
            .aggregate(total=Sum(F('quantite_restante') * F('lot__prix_achat_unitaire')))['total']
            or 0
        )
        total_agents = sum(
            (ligne["valeur_immobilisee"] for ligne in StockAgeService._lignes_stock_retenu_agents(seuil_retention)),
            start=Decimal('0'),
        )
        return total_entrepot + total_superviseur + total_agents

    # ------------------------------------------------------------------
    # API dédiée UI (dashboard surveillance) — entrepôt uniquement.
    #
    # lots_stock_dormant()/count_lots_stock_dormant()/valeur_stock_dormant()
    # ci-dessus restent la source du moteur d'alertes Telegram (monitoring),
    # qui a besoin des 3 origines. L'UI n'a jamais eu vocation à afficher la
    # rétention superviseur/agent avec la même précision que
    # `direction.suivi_distributions` (filtrable par agent/superviseur/
    # produit/période) — les y mélanger induisait en erreur en plus de
    # déclencher le calcul agent (_lignes_stock_retenu_agents, N+1 sur
    # quantite_restante_calculee) à chaque rendu de page, jusqu'à 3 fois par
    # requête (liste + count + valeur) : la cause des ~2400 requêtes SQL
    # observées sur /surveillance/stock-rotation/. Ces méthodes évitent tout
    # calcul agent/superviseur : uniquement des requêtes SQL pures sur
    # LotEntrepot.
    # ------------------------------------------------------------------

    @staticmethod
    def lots_dormants_entrepot(limit=None):
        seuil = StockAgeService._seuil_dormant_entrepot()
        now = timezone.now()

        qs = (
            StockAgeService._queryset_lots_dormants_entrepot(seuil)
            .select_related('produit', 'fournisseur')
            .order_by('date_reception')
        )
        if limit is not None:
            qs = qs[:limit]

        return [
            {
                "origine": "entrepot",
                "id": lot.id,
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "reference_lot": lot.reference_lot,
                "localisation": "Entrepôt central",
                "date_reference": lot.date_reception,
                "quantite_restante": lot.quantite_restante,
                "valeur_immobilisee": lot.quantite_restante * lot.prix_achat_unitaire,
                "jours_ecoules": (now - lot.date_reception).days,
            }
            for lot in qs
        ]

    @staticmethod
    def count_lots_dormants_entrepot():
        seuil = StockAgeService._seuil_dormant_entrepot()
        return StockAgeService._queryset_lots_dormants_entrepot(seuil).count()

    @staticmethod
    def valeur_stock_dormant_entrepot():
        seuil = StockAgeService._seuil_dormant_entrepot()
        return (
            StockAgeService._queryset_lots_dormants_entrepot(seuil)
            .aggregate(total=Sum(F('quantite_restante') * F('prix_achat_unitaire')))['total']
            or 0
        )
