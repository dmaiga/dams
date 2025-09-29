# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
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
    path('ventes/nouvelle/', views.enregistrer_vente, name='enregistrer_vente'),
    path('ventes/liste/', views.liste_ventes, name='liste_ventes'),
    path('api/info-distribution/<int:detail_id>/', views.get_info_distribution, name='api_info_distribution'),
]