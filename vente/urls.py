from django.urls import path
from . import views

app_name = 'vente'

urlpatterns = [
    path('', views.liste_affectations, name='liste_affectations'),
    path('distribuer/', views.creer_distribution, name='creer_distribution'),
    path('distribution/<int:pk>/', views.detail_distribution_superviseur, name='detail_distribution'),
    path('vente/nouvelle/', views.enregistrer_vente, name='enregistrer_vente'),
    path('ventes/', views.historique_ventes, name='historique_ventes'),

    path('ajax/affectations-par-agent/', views.ajax_affectations_par_agent, name='ajax_affectations_par_agent'),
    path('ajax/distributions-par-agent/', views.ajax_distributions_par_agent, name='ajax_distributions_par_agent'),
]
