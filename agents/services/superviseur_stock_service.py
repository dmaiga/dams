from core.models import AffectationLotSuperviseur


class SuperviseurStockService:
    """
    Stock réel d’un superviseur (source de vérité = AffectationLotSuperviseur)
    """

    def __init__(self, superviseur):
        self.superviseur = superviseur

    def get_stock(self):
        stock_par_produit = {}

        affectations = (
            AffectationLotSuperviseur.objects
            .filter(superviseur=self.superviseur)
            .select_related('lot__produit')
        )

        for aff in affectations:
            produit = aff.lot.produit
            pid = produit.id

            if pid not in stock_par_produit:
                stock_par_produit[pid] = {
                    'produit': produit,
                    'quantite_affectee': 0,
                    'quantite_restante': 0,
                    'quantite_distribuee': 0,
                }

            stock_par_produit[pid]['quantite_affectee'] += aff.quantite_initiale
            stock_par_produit[pid]['quantite_restante'] += aff.quantite_restante

        # Calcul dérivé (sûr)
        for data in stock_par_produit.values():
            data['quantite_distribuee'] = (
                data['quantite_affectee'] - data['quantite_restante']
            )

            # garde-fou
            if data['quantite_distribuee'] < 0:
                data['quantite_distribuee'] = 0

        return list(stock_par_produit.values())
