from django.contrib import admin

from bi.models import AjustementPrixAchat


def _est_direction(request):
    if request.user.is_superuser:
        return True
    agent = getattr(request.user, "agent", None)
    return bool(agent and agent.type_agent == "direction")


@admin.register(AjustementPrixAchat)
class AjustementPrixAchatAdmin(admin.ModelAdmin):
    """Saisie append-only : accès réservé à la Direction. Pas d'édition ni de suppression
    une fois enregistré — un ajustement erroné s'annule par un contre-ajustement (nouvelle
    ligne), jamais par une modification de l'historique."""

    list_display = (
        "fournisseur",
        "annee",
        "mois",
        "quantite_concernee",
        "prix_achat_corrige",
        "reference_lot",
        "saisi_par",
        "date_saisie",
    )
    list_filter = ("fournisseur", "annee", "mois")
    readonly_fields = ("saisi_par", "date_saisie")

    def has_module_permission(self, request):
        return _est_direction(request)

    def has_view_permission(self, request, obj=None):
        return _est_direction(request)

    def has_add_permission(self, request):
        return _est_direction(request)

    def has_change_permission(self, request, obj=None):
        return False if obj is not None else _est_direction(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.saisi_par = request.user
        super().save_model(request, obj, form, change)
