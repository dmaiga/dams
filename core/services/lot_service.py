"""Génération de la référence d'un LotEntrepot.

Extrait de ReceptionLotForm.save() (comportement inchangé) pour être
réutilisé par toute création de lot en dehors du formulaire web — ex. la
réception d'une cession via POST /api/cessions/ (marchandise/services.py).
"""

from django.utils import timezone

from core.models import LotEntrepot


def generer_reference_lot():
    """Retourne la prochaine référence disponible au format AAAAMMJJ-NNNN."""
    prefix = timezone.now().strftime("%Y%m%d")
    dernier_lot = LotEntrepot.objects.filter(
        reference_lot__startswith=prefix
    ).order_by('-reference_lot').first()

    if dernier_lot:
        try:
            dernier_num = int(dernier_lot.reference_lot[-4:])
            nouveau_num = dernier_num + 1
        except (ValueError, IndexError):
            nouveau_num = 1
    else:
        nouveau_num = 1

    return f"{prefix}-{nouveau_num:04d}"
