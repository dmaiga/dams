from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.dashboard_finance, name='dashboard_finance'),
    path('superviseur/<int:pk>/', views.detail_solde_superviseur, name='detail_solde_superviseur'),
    path('recouvrer/<int:pk>/', views.recouvrer_superviseur, name='recouvrer_superviseur'),
    path('recouvrement-versement/', views.recouvrement_versement_groupe, name='recouvrement_versement_groupe'),
    path('versement/nouveau/', views.creer_versement, name='creer_versement'),
    path('depense/nouvelle/', views.creer_depense, name='creer_depense'),
    path('versements/', views.historique_versements, name='historique_versements'),
    path('depenses/', views.historique_depenses, name='historique_depenses'),
    path('mes-engagements-champ/', views.mes_engagements_champ, name='mes_engagements_champ'),
    path('engagement-champ/nouveau/', views.creer_engagement_champ_view, name='creer_engagement_champ'),
    path('engagement-champ/<int:pk>/rembourser/', views.rembourser_engagement_champ_view, name='rembourser_engagement_champ'),
]
