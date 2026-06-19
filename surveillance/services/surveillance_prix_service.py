from django.db.models import BooleanField, Case, Count, F, Min, Value, When

from core.models import LotEntrepot, Vente


class SurveillancePrixService:

    @staticmethod
    def get_resume():
        # 1 requête : tous les lots ayant des ventes sous prix d'achat + agrégats
        rows = (
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

        lot_ids = [r['detail_distribution__lot'] for r in rows]

        # 1 requête : hydratation des lots
        lots_map = {
            lot.id: lot
            for lot in LotEntrepot.objects
                .filter(id__in=lot_ids)
                .select_related('produit', 'fournisseur')
        }

        lignes = []
        for row in rows:
            lot = lots_map.get(row['detail_distribution__lot'])
            if lot is None:
                continue
            prix_min = row['prix_min']
            ecart = prix_min - lot.prix_achat_unitaire

            lignes.append({
                "lot": lot,
                "produit": lot.produit,
                "fournisseur": lot.fournisseur,
                "date_reception": lot.date_reception,
                "quantite_initiale": lot.quantite_initiale,
                "prix_achat": lot.prix_achat_unitaire,
                "prix_min": prix_min,
                "ecart": ecart,
                "nb_vendeurs": row['nb_vendeurs'],
                "nb_ventes_rouges": row['nb_ventes_rouges'],
            })

        lignes.sort(key=lambda x: x["ecart"])

        return {
            "stats": {
                "nb_lots_rouges": len(lignes),
                "nb_ventes_rouges": sum(item["nb_ventes_rouges"] for item in lignes),
                "nb_vendeurs_concernes": sum(item["nb_vendeurs"] for item in lignes),
            },
            "lignes": lignes,
        }

    @staticmethod
    def get_detail_lot(lot):
        # 1 requête avec JOIN + annotation CASE pour le flag "rouge"
        ventes = list(
            Vente.objects
            .filter(
                detail_distribution__lot=lot,
                est_supprime=False,
            )
            .select_related('agent', 'agent__superviseur')
            .annotate(
                rouge=Case(
                    When(
                        prix_vente_unitaire__lt=lot.prix_achat_unitaire,
                        then=Value(True),
                    ),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
            .order_by('-date_vente')
        )

        nb_ventes_rouges = sum(1 for v in ventes if v.rouge)

        lignes = [
            {
                "vente": vente,
                "agent": vente.agent,
                "superviseur": vente.agent.superviseur,
                "date": vente.date_vente,
                "prix": vente.prix_vente_unitaire,
                "quantite": vente.quantite,
                "rouge": vente.rouge,
            }
            for vente in ventes
        ]

        # Résumé par agent : uniquement les ventes sous coût, 1 requête
        from django.db.models import Count, Min
        from core.models import Agent as AgentModel
        agent_rows = (
            Vente.objects
            .filter(
                detail_distribution__lot=lot,
                est_supprime=False,
                prix_vente_unitaire__lt=lot.prix_achat_unitaire,
            )
            .values('agent')
            .annotate(
                prix_min=Min('prix_vente_unitaire'),
                nb_ventes_rouges=Count('id'),
            )
            .order_by('prix_min')
        )
        agent_ids = [r['agent'] for r in agent_rows]
        agents_map = {
            a.id: a
            for a in AgentModel.objects.filter(id__in=agent_ids).select_related('superviseur')
        }
        agents_resume = [
            {
                "agent": agents_map[r['agent']],
                "superviseur": agents_map[r['agent']].superviseur,
                "prix_min": r['prix_min'],
                "nb_ventes_rouges": r['nb_ventes_rouges'],
            }
            for r in agent_rows
            if r['agent'] in agents_map
        ]

        return {
            "lot": lot,
            "prix_achat": lot.prix_achat_unitaire,
            "produit": lot.produit,
            "fournisseur": lot.fournisseur,
            "date_reception": lot.date_reception,
            "quantite_initiale": lot.quantite_initiale,
            "nb_ventes_rouges": nb_ventes_rouges,
            "agents_resume": agents_resume,
            "ventes": lignes,
        }
