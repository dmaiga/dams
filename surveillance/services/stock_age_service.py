from datetime import datetime

from django.db.models import F, Max, Q, Sum
from django.utils import timezone

from core.models import Agent, AffectationLotSuperviseur, DetailDistribution, LotEntrepot
from surveillance.constants import (
    DATE_PLANCHER_STOCK,
    DELAI_ROTATION_JOURS,
    DELAI_STOCK_DORMANT_JOURS,
)


class StockAgeService:
    @staticmethod
    def _seuil_rotation():
        return timezone.now() - timezone.timedelta(days=DELAI_ROTATION_JOURS)

    @staticmethod
    def _seuil_dormant():
        return timezone.now() - timezone.timedelta(days=DELAI_STOCK_DORMANT_JOURS)

    # ------------------------------------------------------------------
    # Alerte 1 — rotation lente
    # ------------------------------------------------------------------

    @staticmethod
    def _queryset_agents_sans_vente_recente(seuil):
        # 1 requête : agrégation (Max des ventes non supprimées) + filtre HAVING
        # sur la dernière vente (ou, à défaut, sur la date de distribution).
        return (
            DetailDistribution.objects
            .filter(
                distribution__agent_terrain__isnull=False,
                distribution__date_distribution__lte=seuil,
                distribution__date_distribution__date__gte=DATE_PLANCHER_STOCK,
            )
            .annotate(
                derniere_vente=Max(
                    'vente__date_vente',
                    filter=Q(vente__est_supprime=False),
                )
            )
            .filter(
                Q(derniere_vente__isnull=True)
                | Q(derniere_vente__lte=seuil)
            )
        )

    @staticmethod
    def agents_sans_vente_recente(limit=None):
        seuil = StockAgeService._seuil_rotation()
        qs = (
            StockAgeService._queryset_agents_sans_vente_recente(seuil)
            .values(
                'id',
                'distribution_id',
                'lot',
                'distribution__agent_terrain',
                'distribution__date_distribution',
                'derniere_vente',
            )
            .order_by('distribution__date_distribution')
        )
        if limit is not None:
            qs = qs[:limit]
        rows = list(qs)

        lot_ids = [r['lot'] for r in rows]
        agent_ids = [r['distribution__agent_terrain'] for r in rows]

        lots_map = {
            lot.id: lot
            for lot in LotEntrepot.objects.filter(id__in=lot_ids).select_related('produit')
        }
        agents_map = {
            agent.id: agent
            for agent in Agent.objects.filter(id__in=agent_ids).select_related('superviseur')
        }

        now = timezone.now()
        lignes = []
        for row in rows:
            lot = lots_map.get(row['lot'])
            agent = agents_map.get(row['distribution__agent_terrain'])
            if lot is None or agent is None:
                continue
            derniere_vente = row['derniere_vente']
            date_reference = derniere_vente or row['distribution__date_distribution']
            lignes.append({
                "detail_distribution_id": row['id'],
                "distribution_id": row['distribution_id'],
                "lot": lot,
                "agent": agent,
                "superviseur": agent.superviseur,
                "date_distribution": row['distribution__date_distribution'],
                "derniere_vente": derniere_vente,
                "jours_ecoules": (now - date_reference).days,
            })
        return lignes

    @staticmethod
    def count_agents_sans_vente_recente():
        seuil = StockAgeService._seuil_rotation()
        return StockAgeService._queryset_agents_sans_vente_recente(seuil).count()

    # ------------------------------------------------------------------
    # Alerte 2 — stock dormant (entrepôt central + chez le superviseur)
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
    def lots_stock_dormant(limit=None):
        seuil = StockAgeService._seuil_dormant()
        seuil_date = seuil.date()
        now = timezone.now()

        lots = (
            StockAgeService._queryset_lots_dormants_entrepot(seuil)
            .select_related('produit', 'fournisseur')
            .order_by('date_reception')
        )
        affectations = (
            StockAgeService._queryset_lots_dormants_superviseur(seuil_date)
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

        lignes.sort(key=lambda item: item["date_tri"])
        if limit is not None:
            lignes = lignes[:limit]
        return lignes

    @staticmethod
    def count_lots_stock_dormant():
        seuil = StockAgeService._seuil_dormant()
        return (
            StockAgeService._queryset_lots_dormants_entrepot(seuil).count()
            + StockAgeService._queryset_lots_dormants_superviseur(seuil.date()).count()
        )

    @staticmethod
    def valeur_stock_dormant():
        seuil = StockAgeService._seuil_dormant()
        total_entrepot = (
            StockAgeService._queryset_lots_dormants_entrepot(seuil)
            .aggregate(total=Sum(F('quantite_restante') * F('prix_achat_unitaire')))['total']
            or 0
        )
        total_superviseur = (
            StockAgeService._queryset_lots_dormants_superviseur(seuil.date())
            .aggregate(total=Sum(F('quantite_restante') * F('lot__prix_achat_unitaire')))['total']
            or 0
        )
        return total_entrepot + total_superviseur
