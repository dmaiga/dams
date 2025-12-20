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
            solde = details['solde_vente_actuel']
            total_recouvrements_agents = details['total_recouvrements_agents']
            total_ventes_personnelles = details['total_ventes_personnelles']
            total_ventes_stagiaires = details['total_ventes_stagiaires']
            total_versements = details['total_versements_vente']
            total_depenses = details['total_depenses_vente']
            

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


from django.contrib import admin
from django.utils.html import format_html
from .models import VersementBancaire, Depense

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

# -------------------------
# Admin pour VersementBancaire
# -------------------------
from django.contrib import admin
from .models import VersementBancaire, RecuVersement

class RecuVersementInline(admin.TabularInline):
    model = RecuVersement
    extra = 1
    fields = ('fichier', 'description', 'date_upload')
    readonly_fields = ('date_upload',)

@admin.register(VersementBancaire)
class VersementBancaireAdmin(admin.ModelAdmin):
    inlines = [RecuVersementInline]
    list_display = ('id', 'superviseur', 'montant_vente', 'montant_hors_vente', 'date_versement_reelle')


@admin.register(RecuVersement)
class RecuVersementAdmin(admin.ModelAdmin):
    list_display = ('id', 'versement', 'description', 'date_upload')
    list_filter = ('date_upload', )
    search_fields = ('description', 'versement__id')


from django.contrib import admin
from .models import Dette, PaiementDette, BonusAgent


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

# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum

from .models import PaiementFournisseur




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


