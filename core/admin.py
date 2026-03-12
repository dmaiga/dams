# core/admin.py
from django.contrib import admin
from .models import (
    Agent, Produit, Client, LotEntrepot, Fournisseur,
    DistributionAgent, DetailDistribution, Vente, 
    MouvementStock,Recouvrement,VersementBancaire,
    PaiementFournisseur,RecouvrementSuperviseur,
    Dette, PaiementDette, BonusAgent,Depense,
    AffectationLotSuperviseur,RecuVersement

)
from django.db.models import Sum
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.html import format_html
from .models import FactureLotEntrepot

@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'contact', 'email', 'adresse', 'date_ajout')
    search_fields = ('nom', 'contact', 'email')
    list_filter = ('date_ajout',)

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ['nom', 'description', 'poids_unitaire_kg']
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
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur produit et fournisseur"""
        return super().get_queryset(request).select_related('produit', 'fournisseur')

@admin.register(DistributionAgent)
class DistributionAgentAdmin(admin.ModelAdmin):
    list_display = ['superviseur', 'agent_terrain', 'date_distribution','date_creation']
    list_filter = ['date_distribution', 'superviseur', 'agent_terrain','date_creation']
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur superviseur et agent_terrain"""
        return super().get_queryset(request).select_related('superviseur__user', 'agent_terrain__user')

@admin.register(DetailDistribution)
class DetailDistributionAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'lot_reference',
        'produit_nom',
        'quantite',
        'agent_terrain',
        'superviseur',
        'date_distribution',
    )


    search_fields = (
        'lot__produit__nom',
        'distribution__agent_terrain__user__username',
        'distribution__superviseur__user__username',
    )
    list_filter = (
        'distribution__date_distribution',
    )

    raw_id_fields = ('distribution', 'lot')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'lot__produit',
            'distribution__agent_terrain',
            'distribution__superviseur',
        )

    @admin.display(description="Produit")
    def produit_nom(self, obj):
        return obj.lot.produit.nom
    @admin.display(description="Lot reference")
    def lot_reference(self, obj):
        return obj.lot.reference_lot

    @admin.display(description="Agent terrain")
    def agent_terrain(self, obj):
        return obj.distribution.agent_terrain

    @admin.display(description="Superviseur")
    def superviseur(self, obj):
        return obj.distribution.superviseur

    @admin.display(description="Date distribution")
    def date_distribution(self, obj):
        return obj.distribution.date_distribution



@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'vendeur',
        'client',
        'produit_nom',
        'quantite_affichee',
        'prix_vente_unitaire',
        'date_vente',
        'date_creation',
    )

    list_filter = (
        'date_vente',
        'date_creation',
        'type_vente',
        'mode_paiement',
    )

    search_fields = (
        'agent__user__first_name',
        'agent__user__last_name',
        'client__nom',
        'detail_distribution__lot__produit__nom',
    )

    raw_id_fields = ('agent', 'stagiaire', 'client', 'detail_distribution')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'agent__user',
                'stagiaire__user',
                'client',
                'detail_distribution__lot__produit',
            )
        )

    # ----------------------------
    # AFFICHAGES OPTIMISÉS
    # ----------------------------
    @admin.display(description="Vendeur")
    def vendeur(self, obj):
        return obj.nom_vendeur_complet

    @admin.display(description="Produit")
    def produit_nom(self, obj):
        return obj.detail_distribution.lot.produit.nom

    @admin.display(description="Quantité")
    def quantite_affichee(self, obj):
        produit = obj.detail_distribution.lot.produit

        if produit.poids_unitaire_kg:
            return f"{obj.quantite}"
        return f"{obj.quantite}"


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ['produit', 'type_mouvement', 'quantite', 'date_mouvement']
    list_filter = ['type_mouvement', 'date_mouvement']
    search_fields = ['produit__nom']
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur produit"""
        return super().get_queryset(request).select_related('produit')


@admin.register(Recouvrement)
class RecouvrementAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'agent_nom',
        'superviseur_nom',
        'montant_recouvre',
        'date_recouvrement',
        'date_creation',
    )

    list_filter = (
        'agent',
        'superviseur',
        'date_recouvrement',
    )

    search_fields = (
        'agent__user__username',
        'agent__user__first_name',
        'agent__user__last_name',
        'superviseur__user__username',
        'superviseur__user__first_name',
        'superviseur__user__last_name',
    )

    ordering = ('-date_recouvrement',)

    readonly_fields = ('date_creation',)

    raw_id_fields = ('agent', 'superviseur')

    # 🔑 OPTIMISATION CRITIQUE
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'agent__user',
                'superviseur__user',
            )
        )

    # -------------------------
    # AFFICHAGE SAFE & RAPIDE
    # -------------------------
    @admin.display(description="Agent")
    def agent_nom(self, obj):
        return obj.agent.full_name if obj.agent else "—"

    @admin.display(description="Superviseur")
    def superviseur_nom(self, obj):
        return obj.superviseur.full_name if obj.superviseur else "—"



@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = [
        'nom_complet',
        'type_agent',
        'superviseur',
        'salaire_base_personnel',
        'telephone',
        'date_debut_fonction',
        'statut_actif',
        'ajustement_solde',
        'statistiques_agent',
    ]

    list_editable = ['ajustement_solde']
    list_filter = ['type_agent', 'est_actif']
    search_fields = [
        'user__first_name',
        'user__last_name',
        'user__username',
        'telephone',
    ]
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur user et superviseur"""
        return super().get_queryset(request).select_related('user', 'superviseur__user')

    actions = ['activer_agents', 'desactiver_agents']

    # =========================
    # AFFICHAGES
    # =========================

    def nom_complet(self, obj):
        return obj.full_name
    nom_complet.short_description = "Nom complet"

    def statut_actif(self, obj):
        if obj.est_actif:
            return format_html(
                '<span style="color: green; font-weight: bold;">✔ Actif</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✖ Inactif</span>'
        )
    statut_actif.short_description = "Statut"

    # =========================
    # ACTIONS ADMIN
    # =========================

    @admin.action(description="✅ Activer les agents sélectionnés")
    def activer_agents(self, request, queryset):
        queryset.update(est_actif=True)

    @admin.action(description="⛔ Désactiver les agents sélectionnés")
    def desactiver_agents(self, request, queryset):
        queryset.update(est_actif=False)

    # =========================
    # STATISTIQUES
    # =========================

    def statistiques_agent(self, obj):
        """
        Statistiques FINANCIÈRES & MÉTIER
        Basées UNIQUEMENT sur les nouvelles propriétés valides
        """

        if obj.est_agent_terrain:
            return (
                f"💼 Ventes: {obj.total_ventes:,.0f} FCFA | "
                f"💵 Recouvré: {obj.total_recouvre:,.0f} FCFA | "
                f"📥 En possession: {obj.argent_en_possession:,.0f} FCFA"
            )

        if obj.est_superviseur:
            solde = obj.solde_reel_superviseur

            couleur = "green" if solde <= 0 else "red"

            return format_html(
                "📦 Recouvré agents: <b>{}</b> FCFA | "
                "💸 Dépenses: <b>{}</b> FCFA | "
                "🏦 Versé: <b>{}</b> FCFA | "
                "💰 Solde: <b style='color:{}'>{}</b> FCFA",
                f"{obj.total_recouvre_agents:,.0f}",
                f"{obj.total_depenses_superviseur:,.0f}",
                f"{obj.total_versements_superviseur:,.0f}",
                couleur,
                f"{solde:,.0f}"
            )
        
        if obj.est_rot:
            return "🧠 Responsable Opérations & Trésorerie"


        if obj.est_direction:
            return "👔 Direction"


        if obj.est_stagiaire:
            vente = Vente.objects.filter(stagiaire=obj).first()
            tuteur = vente.agent.full_name if vente and vente.agent else "—"

            return (
                f"🧪 Stagiaire | "
                f"Ventes: {obj.total_ventes:,.0f} FCFA | "
                f"Tuteur: {tuteur}"
            )


        return "—"

    statistiques_agent.short_description = "📊 Statistiques"


# -------------------------
# Admin pour Depense
# -------------------------
@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'versement',
        'montant',
        'description',
        'date_depense',
        'date_creation'
    ]
    list_filter = ['date_depense', 'versement__superviseur']
    search_fields = ['description', 'versement__superviseur__user__username']
    ordering = ['-date_depense']
    readonly_fields = ['date_creation']
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur versement et superviseur"""
        return super().get_queryset(request).select_related('versement__superviseur__user')

# -------------------------
# Admin pour VersementBancaire
# -------------------------


class RecuVersementInline(admin.TabularInline):
    model = RecuVersement
    extra = 1
    fields = ('fichier', 'description', 'date_upload')
    readonly_fields = ('date_upload',)

@admin.register(VersementBancaire)
class VersementBancaireAdmin(admin.ModelAdmin):
    inlines = [RecuVersementInline]
    list_display = ('id', 'effectue_par', 'montant_vente', 'montant_hors_vente', 'date_versement_reelle')
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur effectue_par et superviseur"""
        return super().get_queryset(request).select_related('effectue_par__user', 'superviseur__user')


@admin.register(RecuVersement)
class RecuVersementAdmin(admin.ModelAdmin):
    list_display = ('id', 'versement', 'description', 'date_upload')
    list_filter = ('date_upload', )
    search_fields = ('description', 'versement__id')
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur versement et superviseur"""
        return super().get_queryset(request).select_related('versement__superviseur__user')



# ==============================
# INLINE POUR LES PAIEMENTS
# ==============================
class PaiementDetteInline(admin.TabularInline):
    model = PaiementDette
    extra = 1
    readonly_fields = ('date_paiement',)


# ==============================
# ADMIN DETTE
# ==============================
@admin.register(Dette)
class DetteAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'vente',
        'montant_total',
        'montant_restant',
        'statut',
        'date_creation',
        'date_echeance',
        'nom_localite',
    )
    
    list_filter = ('statut', 'date_echeance', 'date_creation', 'nom_localite')
    
    search_fields = (
        'vente__client__nom',
        'nom_localite',
    )

    readonly_fields = ('date_creation', 'date_reglement')

    inlines = [PaiementDetteInline]
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur vente et client"""
        return super().get_queryset(request).select_related('vente__client')


# ==============================
# ADMIN PAIEMENT DETTE
# ==============================
@admin.register(PaiementDette)
class PaiementDetteAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'dette',
        'montant',
        'date_paiement',
        'mode_paiement',
        'reference',
    )
    list_filter = ('mode_paiement', 'date_paiement')
    search_fields = ('reference', 'dette__vente__client__nom')
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur dette et client"""
        return super().get_queryset(request).select_related('dette__vente__client')

@admin.register(PaiementFournisseur)
class PaiementFournisseurAdmin(admin.ModelAdmin):

    list_display = (
        'date_paiement',
        'date_reception_lot',
        'fournisseur',
        'produit',
        'lot',
        'montant',
        'dette_lot',
        'total_paye_lot',
        'reste_a_payer_lot',
        'statut_lot',
    )

    list_filter = (
        'fournisseur',
        'lot__produit',
        'date_paiement',
    )

    search_fields = (
        'fournisseur__nom',
        'lot__reference_lot',
        'lot__produit__nom',
    )

    autocomplete_fields = (
        'fournisseur',
        'lot',
        'superviseur',
    )
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur lot, fournisseur et produit"""
        return super().get_queryset(request).select_related('lot__produit', 'lot__fournisseur', 'fournisseur')

    # =========================
    # COLONNES CALCULÉES
    # =========================

    def produit(self, obj):
        return obj.lot.produit.nom if obj.lot else "-"
    produit.short_description = "Produit"

    def dette_lot(self, obj):
        if not obj.lot:
            return "-"
        return f"{obj.lot.valeur_stock_initiale:,.0f} FCFA"
    dette_lot.short_description = "Dette lot"

    def total_paye_lot(self, obj):
        if not obj.lot:
            return "-"
        total = obj.lot.total_paye_lot
        return f"{total:,.0f} FCFA"
    total_paye_lot.short_description = "Payé"

    def reste_a_payer_lot(self, obj):
        if not obj.lot:
            return "-"
        reste = obj.lot.valeur_stock_initiale - obj.lot.total_paye_lot
        return f"{reste:,.0f} FCFA"
    reste_a_payer_lot.short_description = "Reste"

    def statut_lot(self, obj):
        if not obj.lot:
            return "-"
        reste = obj.lot.valeur_stock_initiale - obj.lot.total_paye_lot
        if reste <= 0:
            return "Soldé"
        return "Partiel"
    statut_lot.short_description = "Statut"
    
    def date_reception_lot(self, obj):
        if not obj.lot:
            return "-"
        return obj.lot.date_reception.strftime("%d/%m/%Y")
    date_reception_lot.short_description = "Réception lot"
    date_reception_lot.admin_order_field = "lot__date_reception"

    # =========================
    # SÉCURITÉ MÉTIER
    # =========================

    def save_model(self, request, obj, form, change):
        if not obj.cree_par:
            obj.cree_par = request.user

        if obj.lot:
            total_paye = (
                PaiementFournisseur.objects
                .filter(lot=obj.lot, est_supprime=False)
                .exclude(pk=obj.pk)
                .aggregate(total=Sum('montant'))['total']
                or Decimal('0.00')
            )

            if total_paye + obj.montant > obj.lot.valeur_stock_initiale:
                raise ValidationError(
                    "Le montant dépasse la dette contractuelle du lot."
                )

        super().save_model(request, obj, form, change)


# ==============================
# ADMIN BONUS AGENT
# ==============================
@admin.register(BonusAgent)
class BonusAgentAdmin(admin.ModelAdmin):
    list_display = (
        'agent',
        'nombre_produits_recouverts',
        'total_bonus',
        'date_mise_a_jour',
    )
    
    search_fields = ('agent__user__username', 'agent__user__first_name', 'agent__user__last_name')
    
    readonly_fields = ('date_mise_a_jour',)
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur agent"""
        return super().get_queryset(request).select_related('agent__user')



class RecouvrementSuperviseurAdminForm(ModelForm):
    class Meta:
        model = RecouvrementSuperviseur
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        # 🔒 applique la règle métier du model
        self.instance.full_clean()
        return cleaned_data

@admin.register(RecouvrementSuperviseur)
class RecouvrementSuperviseurAdmin(admin.ModelAdmin):
    form = RecouvrementSuperviseurAdminForm

    list_display = (
        'id',
        'superviseur',
        'rot',
        'montant',
        'cash_disponible',
        'date_recouvrement',
    )

    list_filter = (
        'superviseur',
        'rot',
        'date_recouvrement',
    )

    search_fields = (
        'superviseur__user__username',
        'superviseur__user__first_name',
        'superviseur__user__last_name',
        'rot__user__username',
    )

    ordering = ('-date_recouvrement',)

    readonly_fields = (
        'date_creation',
    )
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur superviseur et rot"""
        return super().get_queryset(request).select_related('superviseur__user', 'rot__user')

    fieldsets = (
        ("Informations principales", {
            "fields": (
                'superviseur',
                'rot',
                'montant',
                'commentaire',
            )
        }),
        ("Dates", {
            "fields": (
                'date_recouvrement',
                'date_creation',
            )
        }),
    )

    # 🧠 INFO CONTEXTUELLE (lecture seule)
    def cash_disponible(self, obj):
        if not obj.superviseur:
            return "-"
    
        cash = obj.superviseur.cash_disponible_superviseur or 0
        cash_str = f"{cash:,.0f} FCFA"
    
        return format_html("<b>{}</b>", cash_str)
    
    cash_disponible.short_description = "Cash dispo superviseur"

@admin.register(AffectationLotSuperviseur)
class AffectationLotSuperviseurAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'lot_reference',
        'produit_nom',
        'superviseur',
        'quantite_resume',
        'prix_gros',
        'prix_detail',
        'date_affectation',
        'attribue_par',
    )

    list_filter = (
        'superviseur',
        'attribue_par',
        'date_affectation',
    )

    search_fields = (
        'lot__produit__nom',
        'superviseur__user__first_name',
        'superviseur__user__last_name',
    )

    ordering = ('-date_affectation',)

    readonly_fields = (
        'quantite_initiale',
        'quantite_restante',
        'attribue_par',
        'created_at',
    )

    raw_id_fields = ('lot', 'superviseur', 'attribue_par')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'lot__produit',
                'superviseur__user',
                'attribue_par__user',
            )
        )

    @admin.display(description="Produit")
    def produit_nom(self, obj):
        return obj.lot.produit.nom
    @admin.display(description="Lot")
    def lot_reference(self, obj):
        return obj.lot.reference_lot

 
@admin.register(FactureLotEntrepot)
class FactureLotEntrepotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lot",
        "montant",
        "date_upload",
    )

    list_editable = (
        "montant",
    )

    readonly_fields = (
        "date_upload",
        "fichier",
    )
    
    def get_queryset(self, request):
        """Optimise les requêtes pour éviter N+1 sur lot et produit"""
        return super().get_queryset(request).select_related('lot__produit', 'lot__fournisseur')


