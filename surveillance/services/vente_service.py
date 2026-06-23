from decimal import Decimal

from django.db.models import Case, DecimalField, ExpressionWrapper, F, Sum, When

from core.models import Vente

# Équivalent ORM de la propriété Vente.quantite_en_kg :
#   - produit conditionné (poids_unitaire_kg non nul) : quantite * poids_unitaire_kg
#   - produit vrac (poids_unitaire_kg nul)            : quantite
KG_EXPRESSION = ExpressionWrapper(
    Case(
        When(
            detail_distribution__lot__produit__poids_unitaire_kg__isnull=False,
            then=F('quantite') * F('detail_distribution__lot__produit__poids_unitaire_kg'),
        ),
        default=F('quantite'),
        output_field=DecimalField(max_digits=14, decimal_places=4),
    ),
    output_field=DecimalField(max_digits=14, decimal_places=4),
)


class VenteSurveillanceService:

    @staticmethod
    def kg_vendus(date_debut, date_fin, superviseur=None, produit=None):
        from surveillance.constants import DATE_PLANCHER_VENTES
        qs = Vente.objects.filter(
            date_vente__date__gte=max(date_debut, DATE_PLANCHER_VENTES),
            date_vente__date__lte=date_fin,
            est_supprime=False,
        )
        if superviseur:
            qs = qs.filter(agent__superviseur=superviseur)
        if produit:
            qs = qs.filter(detail_distribution__lot__produit=produit)

        result = qs.aggregate(total=Sum(KG_EXPRESSION))
        return result['total'] or Decimal('0')
