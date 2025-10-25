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
    list_display = ['superviseur', 'agent_terrain', 'date_distribution']
    list_filter = ['date_distribution', 'superviseur', 'agent_terrain']

@admin.register(DetailDistribution)
class DetailDistributionAdmin(admin.ModelAdmin):
    list_display = ['distribution', 'lot', 'quantite', 'prix_gros', 'prix_detail']
    list_filter = ['distribution__date_distribution']

@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ['agent', 'client', 'detail_distribution', 'quantite', 'prix_vente_unitaire', 'date_vente']
    list_filter = ['date_vente', 'agent', 'client']

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
    search_fields = ('agent__nom', 'superviseur__nom')
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
            total_versements = details['total_versements']
            total_depenses = details['total_depenses']

            return (
                f"🧾 Recouvrements: {total_recouvrements_agents:,} FCFA | "
                f"Ventes pers.: {total_ventes_personnelles:,} FCFA | "
                f"Versements: {total_versements:,} FCFA | "
                f"Dépenses: {total_depenses:,} FCFA | "
                f"💰 Solde: {solde:,} FCFA"
            )

        elif obj.est_agent_terrain:
            return (
                f"Ventes: {obj.total_ventes:,} FCFA | "
                f"Recouvré: {obj.total_recouvre:,} FCFA | "
                f"À recouvrir: {obj.argent_en_possession:,} FCFA"
            )

        elif obj.est_direction:
            return "👔 Membre de la direction"

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
