from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from marchandise.permissions import HasDamsChampsAPIKey
from marchandise.serializers import CessionReceptionSerializer
from marchandise.services import CessionReceptionService


class CessionReceptionAPIView(APIView):
    """
    POST /api/cessions/

    Reçoit une cession déclarée côté dams_champs (app `cessions`) et la
    matérialise en LotEntrepot de stock central. dams_champs reste la
    source de vérité de la notion métier "cession" — `dams` ne fait que la
    recevoir et l'enregistrer (voir docs/API_CESSIONS.md).

    Vue volontairement mince : validation du payload (serializer) puis
    délégation complète à CessionReceptionService, qui porte la logique
    métier (résolution produit/agent/fournisseur, atomicité, idempotence).
    """

    permission_classes = [HasDamsChampsAPIKey]

    def post(self, request):
        serializer = CessionReceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            lot, cree = CessionReceptionService.recevoir_cession(
                idempotency_key=data['idempotency_key'],
                produit_nom=data['produit'],
                quantite=data['quantite'],
                prix_unitaire=data['prix_cession'],
                date_cession=data['date_cession'],
            )
        except ValidationError as exc:
            detail = exc.message if hasattr(exc, 'message') else str(exc)
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'status': 'created' if cree else 'already_exists',
                'idempotency_key': str(lot.cession_idempotency_key),
                'lot_id': lot.pk,
                'reference_lot': lot.reference_lot,
            },
            status=status.HTTP_201_CREATED if cree else status.HTTP_200_OK,
        )
