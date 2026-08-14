import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasDamsChampsAPIKey(BasePermission):
    """
    Autorise uniquement les requêtes portant la clé API dams_champs dans
    l'en-tête 'X-Api-Key'. Sens inverse du mécanisme existant côté
    analyse_champ (settings.DAMS_DISTRIBUTION_API_KEY, où `dams` est
    l'appelant vers dams_agro) : ici `dams` est le serveur qui reçoit,
    authentifié par settings.DAMS_CHAMPS_API_KEY.
    """

    def has_permission(self, request, view):
        expected = getattr(settings, 'DAMS_CHAMPS_API_KEY', '')
        provided = request.headers.get('X-Api-Key', '')

        if not expected or not provided:
            return False

        return hmac.compare_digest(provided, expected)
