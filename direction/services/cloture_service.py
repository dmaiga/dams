from decimal import Decimal
from django.db.models import Sum, F, ExpressionWrapper, DecimalField

from core.models import (
    Vente,
    Recouvrement,
    Depense,
    VersementBancaire
)

def calculer_solde_periode(superviseur, date_debut, date_fin, solde_ouverture):
    """
    Calcule le solde de clôture sur une période réelle.
    """

    ventes = Vente.objects.filter(
        agent=superviseur,
        date_vente__date__range=(date_debut, date_fin),
        est_supprime=False
    ).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantite') * F('prix_vente_unitaire'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
    )['total'] or Decimal('0.00')

    recouvrements = Recouvrement.objects.filter(
        superviseur=superviseur,
        date_recouvrement__date__range=(date_debut, date_fin)
    ).aggregate(
        total=Sum('montant_recouvre')
    )['total'] or Decimal('0.00')

    depenses = Depense.objects.filter(
        versement__superviseur=superviseur,
        date_depense__date__range=(date_debut, date_fin)
    ).aggregate(
        total=Sum('montant')
    )['total'] or Decimal('0.00')

    versements = VersementBancaire.objects.filter(
        superviseur=superviseur,
        date_versement_reelle__date__range=(date_debut, date_fin)
    ).aggregate(
        total=Sum('montant_vente')
    )['total'] or Decimal('0.00')

    solde_cloture = (
        solde_ouverture
        + ventes
        + recouvrements
        - depenses
        - versements
    )

    return {
        "ventes": ventes,
        "recouvrements": recouvrements,
        "depenses": depenses,
        "versements": versements,
        "solde_cloture": solde_cloture
    }
