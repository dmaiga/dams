from django.core.exceptions import PermissionDenied

from core.services.acces import est_verificateur_restreint

# Sections fermées au « Vérificateur général » (menu déjà masqué dans base_admin.html).
PREFIXES_FERMES_VERIFICATEUR = ("/champs/",)


class VerificateurRestreintMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(PREFIXES_FERMES_VERIFICATEUR) and est_verificateur_restreint(request.user):
            raise PermissionDenied
        return self.get_response(request)
