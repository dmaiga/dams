# urls.py
from django.urls import path
from . import views

urlpatterns = [
#tableau_de_bord
  path('tableau-de-bord/superviseur/', views.tableau_de_bord_superviseur, name='tableau_de_bord_superviseur'),
  path('dashboard/', views.tableau_de_bord_rot, name='dashboard_rot'),
  path('agent/dashboard/', views.dashboard_agent, name='dashboard_agent'),
  
  path('sup/agent/liste/', views.liste_agents_sup, name='liste_agents_sup'),
  path('sup/agent/<int:agent_id>/', views.detail_agent_sup, name='detail_agent_sup'),
  path('sup/agents/creer/', views.creer_agent, name='creer_agent'),
  path('sup/agents/modifier/<int:agent_id>/', views.modifier_agent, name='modifier_agent'),

  path('affectation/lot', views.superviseur_lots_affectes, name='superviseur_lots_affectes'),
  path('affectation/agent', views.distribuer_lot_agent, name='distribuer_lot_agent'),

    path('vente/agent', views.vente_superviseur_simplifiee, name='vente_superviseur_simplifiee'),

  path('sup/distribution/liste', views.liste_distribution_sup, name='liste_distribution_sup'),

  path('affectation/liste_rot', views.rot_affectations_liste, name='rot_affectations_liste'),
  path('affectation/creer_rot', views.affecter_lot_superviseur, name='affecter_lot_superviseur'),
  path("rot/agents/", views.liste_agents_rot, name="liste_agents_rot"),
  path("rot/agents/<int:agent_id>/", views.detail_agent_rot, name="detail_agent_rot"),
 
  path(
        "rot/recouvrement/superviseur/",
        views.recouvrer_superviseur,
        name="recouvrer_superviseur"
    ),
    
]