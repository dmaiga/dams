"""Aide partagee pour journaliser une CorrectionAdministrative (sprint-13).

Utilisee par les services de correction de marchandise/ et vente/ — evite de
repeter la resolution ContentType a chaque appelant.
"""

from django.contrib.contenttypes.models import ContentType

from core.models import CorrectionAdministrative


def enregistrer_correction(
    *,
    cible,
    type_correction,
    motif,
    utilisateur,
    anciennes_valeurs,
    nouvelles_valeurs,
):
    return CorrectionAdministrative.objects.create(
        utilisateur=utilisateur,
        content_type=ContentType.objects.get_for_model(type(cible)),
        object_id=cible.pk,
        type_correction=type_correction,
        motif=motif,
        anciennes_valeurs=anciennes_valeurs,
        nouvelles_valeurs=nouvelles_valeurs,
    )
