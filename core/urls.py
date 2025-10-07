# urls.py
from django.urls import path
from . import views
from  .views import DashboardView,PerformanceAgentsView,AnalyseAgentsView,AnalyseClientsView,AnalyseProduitsView
urlpatterns = [
    # Dashboard
  
    path('dashboard/agent/', views.dashboard_agent, name='dashboard_agent'),
    # Agents
    path('agents/', views.liste_agents, name='liste_agents'),
    path('agents/<int:agent_id>/', views.detail_agent, name='detail_agent'),
    path('agents/creer/', views.creer_agent, name='creer_agent'),
    path('agents/modifier/<int:agent_id>/', views.modifier_agent, name='modifier_agent'),
    path('agents/supprimer/<int:agent_id>/', views.supprimer_agent, name='supprimer_agent'),    
# Entrepôt
    path('entrepot/reception/', views.reception_lot, name='reception_lot'),
    path('entrepot/lots/', views.liste_lots, name='liste_lots'),
    path('agent/mon-stock/', views.mon_stock, name='mon_stock'),
# Distribution
    path('distribuer/', views.distribuer_produits_agent, name='distribuer_produits'),
    path('distribution/<int:distribution_id>/modifier/', views.modifier_distribution, name='modifier_distribution'),
    path('distribution/<int:distribution_id>/supprimer/', views.supprimer_distribution, name='supprimer_distribution'),
    path('distribution/<int:distribution_id>/restaurer/', views.restaurer_distribution, name='restaurer_distribution'),
    path('distributions/', views.liste_distributions, name='liste_distributions'),
    path('distribution/<int:distribution_id>/', views.detail_distribution, name='detail_distribution'),
    path('api/stock-produit/<int:produit_id>/', views.get_stock_produit, name='get_stock_produit'),
    path('api/stock-produit-date/', views.get_stock_produit_a_date, name='get_stock_produit_date'),
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
    path('admin/ventes/', views.toutes_les_ventes, name='toutes_les_ventes'),
    path('admin/dettes/', views.toutes_les_dettes, name='toutes_les_dettes'),
    path('admin/bonus/', views.tous_les_bonus, name='tous_les_bonus'),
    
    # API
    path('api/info-distribution/<int:detail_id>/', views.get_info_distribution, name='get_info_distribution'),
#factures
    path('factures/entrepot/', views.liste_factures_entrepot, name='liste_factures_entrepot'),
    path('factures/depots/', views.liste_factures, name='liste_factures'),
    path('lots/<int:lot_id>/', views.detail_lot, name='detail_lot'),
    path('factures/creer/', views.creer_facture, name='creer_facture'),
    path('factures/<int:facture_id>/modifier/', views.modifier_facture, name='modifier_facture'),
    path('factures/<int:facture_id>/supprimer/', views.supprimer_facture, name='supprimer_facture'),
#Clients
    path('clients/', views.ClientListView.as_view(), name='liste_clients'),
    path('clients/ajouter/', views.ClientCreateView.as_view(), name='ajouter_client'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='detail_client'),
    path('clients/<int:pk>/modifier/', views.ClientUpdateView.as_view(), name='modifier_client'),
    path('clients/<int:pk>/supprimer/', views.ClientDeleteView.as_view(), name='supprimer_client'),
#tableau_de_bord
   path('tableau-de-bord/superviseur/', views.tableau_de_bord_superviseur, name='tableau_de_bord_superviseur'),
   path('tableau-de-bord/agent/<int:agent_id>/', views.vue_detail_agent, name='vue_detail_agent'),
#RECOUVREMENT
    path('recouvrement/agents/', views.liste_agents_recouvrement, name='liste_agents_recouvrement'),
    path('agent/<int:agent_id>/recouvrement/creer/', views.creer_recouvrement, name='creer_recouvrement'),
    path('agent/<int:agent_id>/recouvrement/historique/', views.historique_recouvrement, name='historique_recouvrement'),
path('agent/<int:agent_id>/recouvrement/historique/complet/', views.detail_historique, name='detail_historique'),
#ADMIN
    path('', DashboardView.as_view(), name='dashboard'),
    path('analyses/bonus', views.tous_les_bonus, name='tous_les_bonus'), 
    path('analyses/dettes', views.toutes_les_dettes, name='toutes_les_dettes'),
    path('analyses/ventes', views.toutes_les_ventes, name='toutes_les_ventes'),  
    path('performances/agents/', PerformanceAgentsView.as_view(), name='performance_agents'),
    path('analyses/produits/', AnalyseProduitsView.as_view(), name='analyse_produits'),
    path('analyses/clients/', AnalyseClientsView.as_view(), name='analyse_clients'),
    path('analyses/agents/', AnalyseAgentsView.as_view(), name='analyse_agents'),

]