from django.utils import timezone
from django.db.models import Sum, Avg
from datetime import timedelta
from core.models import Produit, LotEntrepot, Vente

class ProduitService:

    @staticmethod
    def get_kpis_global():
        lots = LotEntrepot.objects.all()

        stock_total = lots.aggregate(total=Sum('quantite_restante'))['total'] or 0

        valeur_stock = sum(
            lot.quantite_restante * float(lot.prix_achat_unitaire)
            for lot in lots
        )

        produits = Produit.objects.all()
        rotations = []
        for produit in produits:
            achats = LotEntrepot.objects.filter(produit=produit)
            stock = sum(l.quantite_restante for l in achats)

            ventes_30j = Vente.objects.filter(
                detail_distribution__lot__produit=produit,
                date_vente__gte=timezone.now() - timedelta(days=30)
            ).aggregate(total=Sum('quantite'))['total'] or 0

            if stock > 0 and ventes_30j > 0:
                rotations.append((ventes_30j / stock) * 100)

        rotation_moy = sum(rotations)/len(rotations) if rotations else 0

        produits_critiques = lots.filter(quantite_restante__lt=5).count()

        ca_30j = sum(
            v.quantite * v.prix_vente_unitaire
            for v in Vente.objects.filter(
                date_vente__gte=timezone.now() - timedelta(days=30)
            )
        )

        return {
            "stock_total": stock_total,
            "valeur_stock": valeur_stock,
            "rotation_moy": rotation_moy,
            "produits_critiques": produits_critiques,
            "ca_30j": ca_30j,
        }

    @staticmethod
    def get_produits(fournisseur_id=None):
        produits = Produit.objects.all()
        data = []

        for produit in produits:
            lots = LotEntrepot.objects.filter(produit=produit)
            if fournisseur_id:
                lots = lots.filter(fournisseur_id=fournisseur_id)

            stock = sum(l.quantite_restante for l in lots)
            prix_achat_moy = lots.aggregate(avg=Avg('prix_achat_unitaire'))['avg'] or 0

            ventes = Vente.objects.filter(
                detail_distribution__lot__produit=produit
            )

            ca_total = sum(v.quantite * v.prix_vente_unitaire for v in ventes)

            data.append({
                "produit": produit,
                "stock": stock,
                "prix_achat_moy": prix_achat_moy,
                "ca_total": ca_total,
                "lots": lots,
            })

        return data
