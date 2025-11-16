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
        # Vérifier que le produit existe et n'est pas supprimé
        produit = Produit.objects.get(id=produit_id, est_supprime=False)
        
        # Récupérer les lots disponibles non supprimés
        lots = LotEntrepot.objects.filter(
            produit=produit,
            quantite_restante__gt=0,
            est_supprime=False
        ).order_by('date_reception')
        
        lots_data = []
        for lot in lots:
            lots_data.append({
                'id': lot.id,
                'reference_lot': lot.reference_lot,
                'quantite_restante': float(lot.quantite_restante),
                'quantite_initiale': float(lot.quantite_initiale),
                'date_reception': lot.date_reception.isoformat(),
                'etat_lot': lot.etat_lot,
                'description_etat': lot.description_etat,
                'prix_achat_unitaire': float(lot.prix_achat_unitaire),
                'unite_mesure': lot.produit.unite_mesure,
            })
        
        return JsonResponse(lots_data, safe=False)
        
    except Produit.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé ou supprimé'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)