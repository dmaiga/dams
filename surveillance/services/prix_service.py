from django.db.models import Count, F, Min

from core.models import Agent, LotEntrepot, Vente


class PrixSurveillanceService:

    @staticmethod
    def ventes_a_perte():
        # 1 requête : lots avec ventes sous prix d'achat + agrégats en DB
        lot_stats = (
            Vente.objects
            .filter(
                est_supprime=False,
                prix_vente_unitaire__lt=F(
                    'detail_distribution__lot__prix_achat_unitaire'
                ),
            )
            .values('detail_distribution__lot')
            .annotate(
                prix_min=Min('prix_vente_unitaire'),
                nb_ventes_rouges=Count('id'),
                nb_vendeurs=Count('agent', distinct=True),
            )
        )

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
                prix_vente_unitaire__lt=F(
                    'detail_distribution__lot__prix_achat_unitaire'
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
