# urls.py
from django.urls import path
from . import views
from  .views import ( 
                         gestion_factures_lot
                     
                     )
urlpatterns = [
    # Dashboard
  
    path('agent/dashboard/', views.dashboard_agent, name='dashboard_agent'),
    # Agents
    path('agents/', views.liste_agents, name='liste_agents'),
    path('agents/<int:agent_id>/', views.detail_agent, name='detail_agent'),
    path('agents/creer/', views.creer_agent, name='creer_agent'),
    path('agents/modifier/<int:agent_id>/', views.modifier_agent, name='modifier_agent'),
    path('agents/supprimer/<int:agent_id>/', views.supprimer_agent, name='supprimer_agent'),    
# FOURNISSEUR
    path('fournisseurs/', views.liste_fournisseurs, name='liste_fournisseurs'),
    path('fournisseur/<int:fournisseur_id>/', views.detail_fournisseur, name='detail_fournisseur'),
    path('fournisseurs/ajouter/', views.creer_fournisseur, name='creer_fournisseur'),
    path('fournisseurs/modifier/<int:fournisseur_id>/', views.modifier_fournisseur, name='modifier_fournisseur'),
    path('fournisseurs/supprimer/<int:fournisseur_id>/', views.supprimer_fournisseur, name='supprimer_fournisseur'),



# Entrepôt
    path('entrepot/reception/', views.reception_lot, name='reception_lot'),
    path('entrepot/lots/', views.liste_lots, name='liste_lots'),
    path('lots/<int:lot_id>/', views.detail_lot, name='detail_lot'),
    path('agent/mon-stock/', views.mon_stock, name='mon_stock'),
# Distribution
    path('distribuer/', views.distribuer_produits_agent, name='distribuer_produits'),
    path('distribution/<int:distribution_id>/modifier/', views.modifier_distribution, name='modifier_distribution'),
    path('distribution/<int:distribution_id>/supprimer/', views.supprimer_distribution, name='supprimer_distribution'),
    path('distribution/<int:distribution_id>/restaurer/', views.restaurer_distribution, name='restaurer_distribution'),
    path('distributions/', views.liste_distributions, name='liste_distributions'),
    path('distribution/<int:distribution_id>/', views.detail_distribution, name='detail_distribution'),

    path('stats-superviseurs/', views.stats_superviseurs, name='stats_superviseurs'),
    path('agent/mes-distributions/', views.mes_distributions, name='mes_distributions'),
# Ventes
# Ventes personnelles
    path('ventes/enregistrer/', views.enregistrer_vente, name='enregistrer_vente'),
    path('ventes/', views.liste_ventes, name='liste_ventes'),
    path('ventes/<int:vente_id>/', views.detail_vente, name='detail_vente'),
    
    # Dettes personnelles
    path('dettes/creer/', views.creer_dette, name='creer_dette'),
    path('dettes/', views.liste_dettes, name='liste_dettes'),
    path('dettes/<int:dette_id>/', views.detail_dette, name='detail_dette'),
    path('dettes/<int:dette_id>/paiement/', views.enregistrer_paiement_dette, name='enregistrer_paiement_dette'),
    
    # Bonus personnel
    path('bonus/', views.consulter_bonus, name='consulter_bonus'),
    
    # Administration (toutes les données)

    path('admin/dettes/', views.toutes_les_dettes, name='toutes_les_dettes'),
    path('admin/bonus/', views.tous_les_bonus, name='tous_les_bonus'),
    
    # API
    path('api/info-distribution/<int:detail_id>/', views.get_info_distribution, name='get_info_distribution'),
#factures
    path(
        'factures/entrepot/lot/<int:lot_id>/',
        gestion_factures_lot,
        name='gestion_factures_lot'
    ),
    path('versement/liste/', views.liste_versement, name='liste_versement'),
    path('versements/<int:versement_id>/', views.detail_versement, name='detail_versement'),
    path('versement/<int:pk>/ajouter-recus/', views.AjouterRecusView.as_view(), name='ajouter_recus'),
    path('versement/creer/', views.creer_versement, name='creer_versement'),
    path('versements/<int:versement_id>/modifier/', views.modifier_versement, name='modifier_versement'),
    path('versements/<int:versement_id>/supprimer/', views.supprimer_versement, name='supprimer_versement'),
    path('recus/', views.recu_liste, name='recu_liste'),
    path('recus/nouveau/', views.recu_create, name='recu_create'),
   
    path('factures/entrepot/', views.liste_factures_entrepot, name='liste_factures_entrepot'),


#Clients
    path('clients/', views.ClientListView.as_view(), name='liste_clients'),
    path('clients/ajouter/', views.ClientCreateView.as_view(), name='ajouter_client'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='detail_client'),
    path('clients/<int:pk>/modifier/', views.ClientUpdateView.as_view(), name='modifier_client'),
    path('clients/<int:pk>/supprimer/', views.ClientDeleteView.as_view(), name='supprimer_client'),
#tableau_de_bord
   path('tableau-de-bord/agent/<int:agent_id>/', views.vue_detail_agent, name='vue_detail_agent'),
   path('tableau-de-bord/stagiare/<int:stagiaire_id>/', views.detail_stagiaire, name='detail_stagiaire'),
#RECOUVREMENT
    path('recouvrement/agents/', views.liste_agents_recouvrement, name='liste_agents_recouvrement'),
    path('agent/<int:agent_id>/recouvrement/creer/', views.creer_recouvrement, name='creer_recouvrement'),
    path('agent/<int:agent_id>/recouvrement/historique/', views.historique_recouvrement, name='historique_recouvrement'),
    path('agent/<int:agent_id>/recouvrement/historique/complet/', views.detail_historique, name='detail_historique'),

#ADMIN

    
    path('direction/analyses/bonus', views.tous_les_bonus, name='tous_les_bonus'), 
    path('direction/analyses/dettes', views.toutes_les_dettes, name='toutes_les_dettes'),

]