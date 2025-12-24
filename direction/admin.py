from django.contrib import admin
from core.models import ClotureMensuelle

@admin.register(ClotureMensuelle)
class ClotureMensuelleAdmin(admin.ModelAdmin):
    list_display = (
        'superviseur',
        'annee',
        'mois',
        'date_debut_periode',
        'date_fin_periode',
        'solde_ouverture',
        'solde_cloture',
        'est_cloture'
    )
    list_filter = ('annee', 'mois', 'est_cloture')
