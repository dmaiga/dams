# urls.py
from django.urls import path
from . import views
from  .views import DashboardView,PerformanceAgentsView
urlpatterns = [
    # Dashboard
   path('', DashboardView.as_view(), name='dashboard'),
    path('dashboard/agent/', views.dashboard_agent, name='dashboard_agent'),
    # Agents
    path('agents/', views.liste_agents, name='liste_agents'),
    path('agents/creer/', views.creer_agent, name='creer_agent'),
    path('agents/modifier/<int:agent_id>/', views.modifier_agent, name='modifier_agent'),
    path('agents/supprimer/<int:agent_id>/', views.supprimer_agent, name='supprimer_agent'),    
# Entrepôt
    path('entrepot/reception/', views.reception_lot, name='reception_lot'),
    path('entrepot/lots/', views.liste_lots, name='liste_lots'),
# Distribution
    path('distribution/nouvelle/', views.distribuer_produits_agent, name='distribuer_produits'),
    path('distribution/liste/', views.liste_distributions, name='liste_distributions'),
    path('distribution/<int:distribution_id>/', views.detail_distribution, name='detail_distribution'),
    path('api/stock-produit/<int:produit_id>/', views.get_stock_produit, name='api_stock_produit'),
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
    path('factures/', views.liste_factures, name='liste_factures'),
    path('factures/creer/', views.creer_facture, name='creer_facture'),
    path('factures/<int:facture_id>/modifier/', views.modifier_facture, name='modifier_facture'),
    path('factures/<int:facture_id>/supprimer/', views.supprimer_facture, name='supprimer_facture'),
#Clients
    path('clients/', views.ClientListView.as_view(), name='liste_clients'),
    path('clients/ajouter/', views.ClientCreateView.as_view(), name='ajouter_client'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='detail_client'),
    path('clients/<int:pk>/modifier/', views.ClientUpdateView.as_view(), name='modifier_client'),
    path('clients/<int:pk>/supprimer/', views.ClientDeleteView.as_view(), name='supprimer_client'),
#statistique
    
    path('performances/agents/', PerformanceAgentsView.as_view(), name='performance_agents'),
]