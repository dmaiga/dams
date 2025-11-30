# views_api.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from .models import LotEntrepot, Produit
@require_GET
def api_lots_disponibles(request):
    produit_id = request.GET.get('produit_id')
    if not produit_id:
        return JsonResponse({'error': 'produit_id requis'}, status=400)

    try:
        produit = Produit.objects.get(id=produit_id, est_supprime=False)

        lots = LotEntrepot.objects.filter(
            produit=produit,
            est_supprime=False
        ).order_by('date_reception')

        lots_data = []

        for lot in lots:
            # Trouver toutes les distributions pour ce lot
            details = DetailDistribution.objects.filter(
                lot=lot,
                est_supprime=False
            )

            # Quantité restante = somme détaillée des stocks de distribution
            somme_dispo = sum([
                float(d.quantite - d.quantite_vendue)
                for d in details
            ])

            lots_data.append({
                'id': lot.id,
                'reference_lot': lot.reference_lot,
                'quantite_restante': somme_dispo,
                'quantite_initiale': float(lot.quantite_initiale),
                'date_reception': lot.date_reception.isoformat(),
                'etat_lot': lot.etat_lot,
                'description_etat': lot.description_etat,
                'prix_achat_unitaire': float(lot.prix_achat_unitaire),
                'unite_mesure': lot.produit.unite_mesure,
            })

        return JsonResponse(lots_data, safe=False)

    except Produit.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé'}, status=404)
