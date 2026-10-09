"""Aide partagee pour journaliser une CorrectionAdministrative (sprint-13).

Utilisee par les services de correction de marchandise/ et vente/ — evite de
repeter la resolution ContentType a chaque appelant.
"""

from django.contrib.contenttypes.models import ContentType

from core.models import CorrectionAdministrative

# Groupe Django des personnes habilitees a surveiller et corriger prix/quantite
# des ventes saisies par les superviseurs (premier garde-fou contre les erreurs
# de saisie et les ecarts de prix). Cree par la migration core.0131.
GROUPE_CORRECTEURS_VENTES = "Correcteurs ventes"


def est_correcteur_ventes(user):
    """mdmaiga (admin) ou membre du groupe « Correcteurs ventes »."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.username == "mdmaiga":
        return True
    return user.groups.filter(name=GROUPE_CORRECTEURS_VENTES).exists()


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
