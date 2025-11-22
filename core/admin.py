# core/admin.py
from django.contrib import admin
from .models import (
    Agent, Produit, Client, LotEntrepot, Fournisseur,
    DistributionAgent, DetailDistribution, Vente, 
    MouvementStock, Facture,Recouvrement,VersementBancaire
)

from .models import Fournisseur

@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'contact', 'email', 'adresse', 'date_ajout')
    search_fields = ('nom', 'contact', 'email')
    list_filter = ('date_ajout',)

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ['nom', 'description']
    search_fields = ['nom']



@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_client', 'contact']
    list_filter = ['type_client']
    search_fields = ['nom']

@admin.register(LotEntrepot)
class LotEntrepotAdmin(admin.ModelAdmin):
    list_display = ['produit', 'fournisseur', 'quantite_initiale', 'quantite_restante', 'prix_achat_unitaire', 'date_reception']
    list_filter = ['produit', 'fournisseur', 'date_reception']
    search_fields = ['produit__nom', 'fournisseur__nom']

@admin.register(DistributionAgent)
class DistributionAgentAdmin(admin.ModelAdmin):
    list_display = ['superviseur', 'agent_terrain', 'date_distribution','date_creation']
    list_filter = ['date_distribution', 'superviseur', 'agent_terrain','date_creation']

@admin.register(DetailDistribution)
class DetailDistributionAdmin(admin.ModelAdmin):
    list_display = ['distribution', 'lot', 'quantite', 'prix_gros', 'prix_detail']
    list_filter = ['distribution__date_distribution']

@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = [
        'agent',
        'client',
        'get_produit',  # ← Nouveau champ calculé
        'detail_distribution',
        'quantite',
        'prix_vente_unitaire',
        'date_vente',
        'date_creation'
    ]
    list_filter = ['date_vente', 'agent', 'client','date_creation']
    search_fields = [
        'agent__user__username', 
        'agent__user__first_name', 
        'agent__user__last_name',
        'detail_distribution__lot__produit__nom'  # Permet rechercher par produit
    ]

    def get_produit(self, obj):
        return obj.detail_distribution.lot.produit.nom if obj.detail_distribution else "-"
    get_produit.short_description = 'Produit'


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ['produit', 'type_mouvement', 'quantite', 'date_mouvement']
    list_filter = ['type_mouvement', 'date_mouvement']
    search_fields = ['produit__nom']

@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ['type_facture', 'agent', 'montant', 'date_depot']
    list_filter = ['type_facture', 'date_depot']

@admin.register(Recouvrement)
class RecouvrementAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent', 'superviseur', 'montant_recouvre', 'date_recouvrement', 'date_creation')
    list_filter = ('agent', 'superviseur', 'date_recouvrement')
    search_fields = [
        'agent__user__username', 
        'agent__user__first_name', 
        'agent__user__last_name',
         # Permet rechercher par produit
    ]
    ordering = ('-date_recouvrement',)
    readonly_fields = ('date_creation',)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = [
        'nom_complet',
        'type_agent',
        'telephone',
        'ajustement_solde',
        'statistiques_agent',
    ]
    list_editable = ['ajustement_solde']
    list_filter = ['type_agent']
    search_fields = [
        'user__first_name',
        'user__last_name',
        'user__username',
        'telephone',
    ]

    def nom_complet(self, obj):
        return obj.full_name
    nom_complet.short_description = "Nom complet"

    def statistiques_agent(self, obj):
        """
        Affiche les principales statistiques selon le type d'agent.
        """
        if obj.est_superviseur:
            # Récupération des données détaillées
            details = obj.detail_solde_superviseur
            solde = details['solde_actuel']
            total_recouvrements_agents = details['total_recouvrements_agents']
            total_ventes_personnelles = details['total_ventes_personnelles']
            total_ventes_stagiaires = details['total_ventes_stagiaires']
            total_versements = details['total_versements']
            total_depenses = details['total_depenses']

            return (
                f"🧾 Recouvrements: {total_recouvrements_agents:,} FCFA | "
                f"Ventes pers.: {total_ventes_personnelles:,} FCFA | "
                f"Ventes stagiaires: {total_ventes_stagiaires:,} FCFA | "
                f"Versements: {total_versements:,} FCFA | "
                f"Dépenses: {total_depenses:,} FCFA | "
                f"💰 Solde: {solde:,} FCFA"
            )

        elif obj.est_agent_terrain:
            return (
                f"Ventes pers.: {obj.total_ventes_personnelles:,} FCFA | "
                f"Ventes stagiaires: {obj.total_ventes_stagiaires:,} FCFA | "
                f"Total: {obj.total_ventes:,} FCFA | "
                f"Recouvré: {obj.total_recouvre:,} FCFA | "
                f"À recouvrir: {obj.argent_en_possession:,} FCFA | "
                f"Stagiaires: {obj.nombre_stagiaires_supervises}"
            )

        elif obj.est_direction:
            return "👔 Membre de la direction"

        elif obj.est_stagiaire:
            tuteur = "Aucun"
            # Trouver le tuteur du stagiaire
            vente_avec_tuteur = Vente.objects.filter(stagiaire=obj).first()
            if vente_avec_tuteur and vente_avec_tuteur.agent:
                tuteur = vente_avec_tuteur.agent.full_name
            
            return (
                f"Ventes: {obj.total_ventes:,} FCFA | "
                f"Tuteur: {tuteur} | "
                f"Statut: {obj.statut_stagiaire}"
            )

        return "—"
    statistiques_agent.short_description = "📊 Statistiques"

from django.contrib import admin
from .models import BonusAgent


@admin.register(BonusAgent)
class BonusAgentAdmin(admin.ModelAdmin):
    list_display = ['agent', 'nombre_produits_recouverts', 'total_bonus', 'date_mise_a_jour']
    list_filter = ['agent']
    readonly_fields = ['nombre_produits_recouverts', 'total_bonus', 'date_mise_a_jour']
    
    # Empêcher l'ajout manuel (se crée automatiquement)
    def has_add_permission(self, request):
        return False

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from decimal import Decimal
from .models import VersementBancaire, Depense

class DepenseInline(admin.TabularInline):
    """Inline pour afficher les dépenses dans l'admin des versements"""
    model = Depense
    extra = 0
    fields = ['montant', 'categorie', 'description', 'date_depense', 'justificatif_link']
    readonly_fields = ['justificatif_link']
    
    def justificatif_link(self, obj):
        if obj.justificatif:
            return format_html(
                '<a href="{}" target="_blank">📎 Voir le justificatif</a>',
                obj.justificatif.url
            )
        return "Aucun justificatif"
    justificatif_link.short_description = "Justificatif"

class VersementBancaireAdmin(admin.ModelAdmin):
    """Configuration admin pour les versements bancaires"""
    
    list_display = [
        'id', 
        'superviseur', 
        'type_versement_display', 
        'montant_verse', 
        'total_depenses_display',
        'montant_net_display',
        'date_versement_reelle',
        'solde_suffisant_display'
    ]
    
    list_filter = [
        'type_versement',
        'date_versement_reelle',
        'superviseur',
    ]
    
    search_fields = [
        'superviseur__user__username',
        'superviseur__user__first_name', 
        'superviseur__user__last_name',
        'details_depenses'
    ]
    
    readonly_fields = [
        'date_creation',
        'total_depenses_calcul',
        'montant_net_calcul',
        'solde_disponible_calcul'
    ]
    
    fieldsets = (
        ('Informations du versement', {
            'fields': (
                'superviseur',
                'type_versement',
                'montant_verse',
                'date_versement_reelle',
            )
        }),
        ('Dépenses et notes', {
            'fields': (
                'details_depenses',
            )
        }),
        ('Calculs et statistiques', {
            'fields': (
                'total_depenses_calcul',
                'montant_net_calcul', 
                'solde_disponible_calcul',
            ),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation',),
            'classes': ('collapse',)
        })
    )
    
    inlines = [DepenseInline]
    
    def type_versement_display(self, obj):
        color = 'green' if obj.type_versement == 'vente' else 'orange'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_type_versement_display()
        )
    type_versement_display.short_description = 'Type'
    type_versement_display.admin_order_field = 'type_versement'
    
    def total_depenses_display(self, obj):
        total = obj.total_depenses_associees
        color = 'red' if total > 0 else 'gray'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            f"{total} FCFA"
        )
    total_depenses_display.short_description = 'Dépenses'
    
    def montant_net_display(self, obj):
        montant_net = obj.montant_net
        color = 'green' if montant_net >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            f"{montant_net} FCFA"
        )
    montant_net_display.short_description = 'Montant net'
    
    def solde_suffisant_display(self, obj):
        if obj.type_versement == 'vente':
            solde_disponible = obj.solde_disponible_vente_avant_versement
            suffisant = obj.montant_net <= solde_disponible
            icon = '✅' if suffisant else '❌'
            color = 'green' if suffisant else 'red'
            return format_html(
                '<span style="color: {};">{} {}</span>',
                color,
                icon,
                "Suffisant" if suffisant else "Insuffisant"
            )
        return "N/A"
    solde_suffisant_display.short_description = 'Solde'
    
    def total_depenses_calcul(self, obj):
        return f"{obj.total_depenses_associees} FCFA"
    total_depenses_calcul.short_description = 'Total des dépenses associées'
    
    def montant_net_calcul(self, obj):
        return f"{obj.montant_net} FCFA"
    montant_net_calcul.short_description = 'Montant net (versé - dépenses)'
    
    def solde_disponible_calcul(self, obj):
        if obj.type_versement == 'vente':
            solde = obj.solde_disponible_vente_avant_versement
            return f"{solde} FCFA"
        return "Non applicable (versement autre)"
    solde_disponible_calcul.short_description = 'Solde disponible avant versement'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('superviseur', 'superviseur__user')
    
    def save_model(self, request, obj, form, change):
        """Validation supplémentaire lors de la sauvegarde depuis l'admin"""
        try:
            obj.clean()  # Appel de la validation du modèle
            super().save_model(request, obj, form, change)
        except Exception as e:
            from django.contrib import messages
            self.message_user(request, f"Erreur de validation: {str(e)}", level=messages.ERROR)

class DepenseAdmin(admin.ModelAdmin):
    """Configuration admin pour les dépenses"""
    
    list_display = [
        'id',
        'superviseur',
        'versement_link',
        'montant',
        'categorie_display',
        'type_versement_display',
        'date_depense',
        'justificatif_present'
    ]
    
    list_filter = [
        'categorie',
        'type_versement',
        'date_depense',
        'versement__superviseur',
    ]
    
    search_fields = [
        'description',
        'superviseur__user__username',
        'superviseur__user__first_name',
        'superviseur__user__last_name',
        'versement__id'
    ]
    
    readonly_fields = [
        'date_creation',
        'impact_solde_info'
    ]
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'superviseur',
                'versement',
                'type_versement',
            )
        }),
        ('Détails de la dépense', {
            'fields': (
                'montant',
                'categorie',
                'description',
                'date_depense',
                'justificatif',
            )
        }),
        ('Informations système', {
            'fields': (
                'impact_solde_info',
                'date_creation',
            ),
            'classes': ('collapse',)
        })
    )
    
    def versement_link(self, obj):
        if obj.versement:
            return format_html(
                '<a href="{}">Versement #{}</a>',
                f"/admin/core/versementbancaire/{obj.versement.id}/change/",
                obj.versement.id
            )
        return "Aucun versement associé"
    versement_link.short_description = 'Versement'
    
    def categorie_display(self, obj):
        colors = {
            'transport': 'blue',
            'communication': 'green', 
            'frais_bancaires': 'purple',
            'materiel': 'orange',
            'autres': 'gray'
        }
        color = colors.get(obj.categorie, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_categorie_display()
        )
    categorie_display.short_description = 'Catégorie'
    
    def type_versement_display(self, obj):
        color = 'green' if obj.type_versement == 'vente' else 'orange'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_type_versement_display()
        )
    type_versement_display.short_description = 'Type versement'
    
    def justificatif_present(self, obj):
        if obj.justificatif:
            return format_html('✅ Oui')
        return format_html('❌ Non')
    justificatif_present.short_description = 'Justificatif'
    
    def impact_solde_info(self, obj):
        if obj.impacte_solde_vente:
            return format_html(
                '<span style="color: orange;">⚠️ Cette dépense impacte le solde des ventes</span>'
            )
        return format_html(
            '<span style="color: green;">✅ Cette dépense n\'impacte pas le solde des ventes</span>'
        )
    impact_solde_info.short_description = 'Impact sur le solde'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('superviseur', 'superviseur__user', 'versement')
    
    def save_model(self, request, obj, form, change):
        """Synchronisation automatique du type_versement avec le versement"""
        if obj.versement:
            obj.type_versement = obj.versement.type_versement
        try:
            obj.clean()
            super().save_model(request, obj, form, change)
        except Exception as e:
            from django.contrib import messages
            self.message_user(request, f"Erreur de validation: {str(e)}", level=messages.ERROR)

# Actions personnalisées pour l'admin
def exporter_versements_excel(modeladmin, request, queryset):
    """Action pour exporter les versements sélectionnés en Excel"""
    # Cette fonction pourrait être implémentée avec pandas ou openpyxl
    from django.http import HttpResponse
    import csv
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="versements.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Superviseur', 'Type', 'Montant versé', 'Dépenses', 'Montant net', 'Date'])
    
    for versement in queryset:
        writer.writerow([
            versement.id,
            versement.superviseur.full_name,
            versement.get_type_versement_display(),
            versement.montant_verse,
            versement.total_depenses_associees,
            versement.montant_net,
            versement.date_versement_reelle.strftime('%d/%m/%Y')
        ])
    
    return response
exporter_versements_excel.short_description = "Exporter les versements sélectionnés en CSV"

def calculer_total_depenses(modeladmin, request, queryset):
    """Action pour calculer le total des dépenses des versements sélectionnés"""
    total_depenses = sum(versement.total_depenses_associees for versement in queryset)
    from django.contrib import messages
    messages.info(request, f"Total des dépenses pour les {queryset.count()} versements sélectionnés: {total_depenses} FCFA")
calculer_total_depenses.short_description = "Calculer le total des dépenses"

# Ajout des actions aux admins
VersementBancaireAdmin.actions = [exporter_versements_excel, calculer_total_depenses]

# Enregistrement des modèles dans l'admin
admin.site.register(VersementBancaire, VersementBancaireAdmin)
admin.site.register(Depense, DepenseAdmin)