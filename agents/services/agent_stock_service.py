# agents/services/agent_stock_service.py

from django.db.models import F
from core.models import DistributionAgent, Vente


class AgentStockService:
    """
    Service métier pour le stock d’un agent terrain
    """

    def __init__(self, agent):
        self.agent = agent

    # =========================
    # Méthode principale
    # =========================
    def get_stock(self):
        stock_par_produit = {}

        distributions = (
            DistributionAgent.objects
            .filter(agent_terrain=self.agent)
            .prefetch_related('detaildistribution_set__lot__produit')
        )

        ventes = (
            Vente.objects
            .filter(agent=self.agent)
            .select_related('detail_distribution__lot__produit')
        )

        # 1️⃣ Quantités distribuées

        for distribution in distributions:
            for detail in distribution.detaildistribution_set.all():
                produit = detail.lot.produit
                pid = produit.id

                if pid not in stock_par_produit:
                    stock_par_produit[pid] = self._init_produit(produit, detail)

                stock_par_produit[pid]['quantite_distribuee'] += detail.quantite

                # ✅ VALEUR FIXÉE PAR LE SUPERVISEUR
                prix_reference = detail.prix_gros or 0
                stock_par_produit[pid]['valeur_distribuee'] += detail.quantite * prix_reference

        # 2️⃣ Quantités vendues
        for vente in ventes:
            produit = vente.detail_distribution.lot.produit
            pid = produit.id

            if pid in stock_par_produit:
                stock_par_produit[pid]['quantite_vendue'] += vente.quantite

        # 3️⃣ Calculs finaux
        for data in stock_par_produit.values():
            data['quantite_restante'] = (
                data['quantite_distribuee'] - data['quantite_vendue']
            )

            if data['quantite_restante'] < 0:
                data['alerte'] = True
                data['quantite_restante'] = 0
            else:
                data['alerte'] = False

            if data['quantite_distribuee'] > 0:
                data['prix_moyen'] = data['valeur_distribuee'] / data['quantite_distribuee']
            else:
                data['prix_moyen'] = 0

            # ✅ valeur réelle du stock restant
            data['valeur_totale'] = data['quantite_restante'] * data['prix_moyen']

        return list(stock_par_produit.values())


    # =========================
    # Helpers
    # =========================
    def _init_produit(self, produit, detail):
        return {
            'produit': produit,
            'quantite_distribuee': 0,
            'quantite_vendue': 0,
            'quantite_restante': 0,
            'prix_gros': detail.prix_gros,
            'prix_detail': detail.prix_detail,
            'valeur_distribuee': 0,   
            'valeur_totale': 0,
            'seuil_alerte': 1,
        }
