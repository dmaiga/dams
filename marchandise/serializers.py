from decimal import Decimal

from django.core.validators import MinValueValidator
from rest_framework import serializers


class CessionReceptionSerializer(serializers.Serializer):
    """
    Validation structurelle du payload POST /api/cessions/ (contrat décrit
    dans docs/API_CESSIONS.md). L'existence du produit et de l'agent de
    réception, ainsi que la création du LotEntrepot, restent la
    responsabilité de `marchandise.services.CessionReceptionService`
    (convention déjà en place dans cette app — voir
    marchandise/APP_MARCHANDISE.md) : ce serializer ne fait aucune requête
    en base, il ne valide que la forme du payload envoyé par dams_champs.
    """

    idempotency_key = serializers.UUIDField(
        help_text="Identifiant stable de la cession côté dams_champs (Cession.idempotency_key)."
    )
    produit = serializers.CharField(
        max_length=150,
        help_text="Nom du produit agricole cédé (core.models.Produit.nom)."
    )
    quantite = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    prix_cession = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Prix unitaire de cession (pas un montant total).",
    )
    date_cession = serializers.DateField()
