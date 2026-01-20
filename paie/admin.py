# paie/admin.py
from django.contrib import admin
from core.models import RegleSalaire, Salaire


@admin.register(RegleSalaire)
class RegleSalaireAdmin(admin.ModelAdmin):
    list_display = (
        "type_agent",
        "dotation_fonction",
        "incentive_par_kg",
        "incentive_par_carton",
        "actif",
    )
    list_filter = ("type_agent", "actif")
    list_editable = (
        "dotation_fonction",
        "incentive_par_kg",
        "incentive_par_carton",
        "actif",
    )


@admin.register(Salaire)
class SalaireAdmin(admin.ModelAdmin):
    list_display = (
        "agent",
        "date_debut",
        "date_fin",
        "salaire_base",
        "incentive",
        "salaire_total",
        "valide",
    )
    list_filter = ("valide", "date_debut")
    readonly_fields = ("genere_le",)
