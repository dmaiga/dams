from decimal import Decimal
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce

from core.models import LotEntrepot

class RotFournisseurService:
    """
    Logique financière ROT (factures uniquement)
    """

    @staticmethod
    def get_suivi_fournisseurs_rot():
        """
        Pour chaque fournisseur :
        - valeur des lots reçus
        - montant total facturé
        - écart (reste à facturer)
        """

        data = (
            LotEntrepot.objects
            .filter(fournisseur__isnull=False)
            .values(
                'fournisseur__id',
                'fournisseur__nom'
            )
            .annotate(
                valeur_lots=Coalesce(
                    Sum(
                        F('quantite_initiale') * F('prix_achat_unitaire'),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal('0.00')
                ),
                montant_facture=Coalesce(
                    Sum('factures__montant'),
                    Decimal('0.00')
                )
            )
            .order_by('fournisseur__nom')
        )

        # Calcul de l’écart ROT (reste à facturer)
        fournisseurs = []
        for row in data:
            reste_a_facturer = max(
                row['valeur_lots'] - row['montant_facture'],
                Decimal('0.00')
            )

            fournisseurs.append({
                'fournisseur_id': row['fournisseur__id'],
                'fournisseur_nom': row['fournisseur__nom'],
                'valeur_lots': row['valeur_lots'],
                'montant_facture': row['montant_facture'],
                'reste_a_facturer': reste_a_facturer,
            })

        return fournisseurs
