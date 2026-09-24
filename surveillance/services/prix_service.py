from decimal import Decimal

from django.db.models import Count, F, Min, Q

from core.models import Agent, LotEntrepot, Vente
from surveillance.constants import DATE_PLANCHER_PRIX, SEUIL_ECART_PRIX_ACHAT, SEUIL_MARGE_MINIMALE

# Agent actif ET (pas de superviseur assigné OU superviseur actif) — ne jamais exclure les
# agents orphelins (cf. _grouper_par_superviseur/sans_superviseur), seulement les agents ou
# superviseurs qui ne travaillent plus (demande mdmaiga, 24/09/2026 : ces alertes n'ont
# vocation qu'à signaler des situations sur lesquelles quelqu'un peut encore agir).
FILTRE_ACTEURS_ACTIFS = Q(agent__est_actif=True) & (
    Q(agent__superviseur__isnull=True) | Q(agent__superviseur__est_actif=True)
)


class PrixSurveillanceService:
    # Marge minimale attendue par vente unitaire — source unique :
    # surveillance.constants.SEUIL_MARGE_MINIMALE (corrigé le 2026-08-13 : ce
    # service définissait auparavant sa propre valeur locale, 45 FCFA, jamais
    # alignée sur la constante déclarée pour cet usage).
    SEUIL_MARGE_MINIMALE = Decimal(str(SEUIL_MARGE_MINIMALE))
    SEUIL_ECART_PRIX_ACHAT = Decimal(str(SEUIL_ECART_PRIX_ACHAT))

    @staticmethod
    def ventes_a_perte(limit=None):
        # 1 requête : lots dont une vente a une marge unitaire < SEUIL_MARGE_MINIMALE.
        lot_stats = (
            Vente.objects
            .filter(
                est_supprime=False,
                date_vente__date__gte=DATE_PLANCHER_PRIX,
                prix_vente_unitaire__lt=(
                    F('detail_distribution__lot__prix_achat_unitaire')
                    + PrixSurveillanceService.SEUIL_MARGE_MINIMALE
                ),
            )
            .values('detail_distribution__lot')
            .annotate(
                prix_min=Min('prix_vente_unitaire'),
                nb_ventes_rouges=Count('id'),
                nb_vendeurs=Count('agent', distinct=True),
                ecart=Min('prix_vente_unitaire') - F('detail_distribution__lot__prix_achat_unitaire')
            )
            .order_by('ecart')
        )

        if limit:
            lot_stats = lot_stats[:limit]

        lot_ids = [r['detail_distribution__lot'] for r in lot_stats]

        if not lot_ids:
            return []

        # 1 requête : hydratation des lots avec leurs relations
        lots_map = {
            lot.id: lot
            for lot in LotEntrepot.objects
                .filter(id__in=lot_ids)
                .select_related('produit', 'fournisseur')
        }

        # 1 requête : agents distincts par lot pour construire la liste "vendeurs"
        vendeurs_rows = (
            Vente.objects
            .filter(
                est_supprime=False,
                date_vente__date__gte=DATE_PLANCHER_PRIX,
                prix_vente_unitaire__lt=(
                    F('detail_distribution__lot__prix_achat_unitaire')
                    + PrixSurveillanceService.SEUIL_MARGE_MINIMALE
                ),
                detail_distribution__lot_id__in=lot_ids,
            )
            .values('detail_distribution__lot', 'agent')
            .distinct()
        )

        agent_ids_par_lot: dict[int, list[int]] = {}
        all_agent_ids: set[int] = set()
        for row in vendeurs_rows:
            lid = row['detail_distribution__lot']
            aid = row['agent']
            agent_ids_par_lot.setdefault(lid, []).append(aid)
            all_agent_ids.add(aid)

        # 1 requête : hydratation des objets Agent
        agents_map = {
            a.id: a
            for a in Agent.objects.filter(id__in=all_agent_ids)
        }

        stats_by_lot = {r['detail_distribution__lot']: r for r in lot_stats}

        resultat = []
        for lot_id, lot in lots_map.items():
            stats = stats_by_lot[lot_id]
            prix_min = stats['prix_min']
            vendeurs = [
                agents_map[aid]
                for aid in agent_ids_par_lot.get(lot_id, [])
                if aid in agents_map
            ]

            resultat.append({
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "date_reception": lot.date_reception,
                "quantite_initiale": lot.quantite_initiale,
                "prix_achat": lot.prix_achat_unitaire,
                "prix_min": prix_min,
                "ecart": prix_min - lot.prix_achat_unitaire,
                "nb_vendeurs": stats['nb_vendeurs'],
                "vendeurs": vendeurs,
                "nb_ventes_rouges": stats['nb_ventes_rouges'],
            })

        resultat.sort(key=lambda x: x["ecart"])
        return resultat

    @staticmethod
    def count_anomalies():
        return (
            Vente.objects
            .filter(
                est_supprime=False,
                date_vente__date__gte=DATE_PLANCHER_PRIX,
                prix_vente_unitaire__lt=(
                    F('detail_distribution__lot__prix_achat_unitaire')
                    + PrixSurveillanceService.SEUIL_MARGE_MINIMALE
                ),
            )
            .values('detail_distribution__lot')
            .distinct()
            .count()
        )

    @staticmethod
    def ventes_sous_marge_minimale():
        """Ventes individuelles (pas de regroupement par lot) dont la marge
        unitaire est strictement sous SEUIL_MARGE_MINIMALE — référence de
        l'alerte Telegram "marge minimale" : contrairement à ventes_a_perte(),
        une ligne = une vente, pas un lot agrégé."""
        ventes = (
            Vente.objects
            .filter(
                FILTRE_ACTEURS_ACTIFS,
                est_supprime=False,
                date_vente__date__gte=DATE_PLANCHER_PRIX,
                prix_vente_unitaire__lt=(
                    F('detail_distribution__lot__prix_achat_unitaire')
                    + PrixSurveillanceService.SEUIL_MARGE_MINIMALE
                ),
            )
            .select_related('agent', 'agent__superviseur', 'detail_distribution__lot__produit')
            .annotate(
                marge=F('prix_vente_unitaire') - F('detail_distribution__lot__prix_achat_unitaire')
            )
            .order_by('marge')
        )

        return [
            {
                "vente": vente,
                "agent": vente.agent,
                "superviseur": vente.agent.superviseur,
                "produit": vente.detail_distribution.lot.produit,
                "prix_vente": vente.prix_vente_unitaire,
                "marge": vente.marge,
            }
            for vente in ventes
        ]

    @staticmethod
    def ventes_ecart_prix_achat_suspect():
        """Ventes individuelles dont le prix de vente dépasse le prix d'achat de plus de
        SEUIL_ECART_PRIX_ACHAT — repli volontairement simple pour repérer une erreur de
        saisie probable (ex. un zéro de trop) sur un prix anormalement HAUT, sans jugement
        sur la rentabilité (cf. SEUIL_ECART_PRIX_ACHAT). Complémentaire de
        ventes_sous_marge_minimale, qui ne couvre que les prix trop BAS."""
        ventes = (
            Vente.objects
            .filter(
                FILTRE_ACTEURS_ACTIFS,
                est_supprime=False,
                date_vente__date__gte=DATE_PLANCHER_PRIX,
                prix_vente_unitaire__gt=(
                    F('detail_distribution__lot__prix_achat_unitaire')
                    + PrixSurveillanceService.SEUIL_ECART_PRIX_ACHAT
                ),
            )
            .select_related('agent', 'agent__superviseur', 'detail_distribution__lot__produit')
            .annotate(
                ecart=F('prix_vente_unitaire') - F('detail_distribution__lot__prix_achat_unitaire')
            )
            .order_by('-ecart')
        )

        return [
            {
                "vente": vente,
                "agent": vente.agent,
                "superviseur": vente.agent.superviseur,
                "produit": vente.detail_distribution.lot.produit,
                "prix_achat": vente.detail_distribution.lot.prix_achat_unitaire,
                "prix_vente": vente.prix_vente_unitaire,
                "ecart": vente.ecart,
            }
            for vente in ventes
        ]
