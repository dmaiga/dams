from core.models import AffectationLotSuperviseur

from django.db.models import Sum, F

class SuperviseurStockService:

    def __init__(self, superviseur):
        self.superviseur = superviseur

    def get_stock(self):
        qs = (
            AffectationLotSuperviseur.objects
            .filter(superviseur=self.superviseur)
            .values(
                'lot__produit',
                'lot__produit__nom',
                'lot__produit__poids_unitaire_kg',
            )
            .annotate(
                quantite_affectee=Sum('quantite_initiale'),
                quantite_restante=Sum('quantite_restante'),
            )
        )

        result = []
        for row in qs:
            affectee = row['quantite_affectee'] or 0
            restante = row['quantite_restante'] or 0

            result.append({
                'produit_id': row['lot__produit'],
                'produit_nom': row['lot__produit__nom'],
                'poids_unitaire_kg': row['lot__produit__poids_unitaire_kg'],
                'quantite_affectee': affectee,
                'quantite_restante': restante,
                'quantite_distribuee': max(affectee - restante, 0),
            })

        return result
