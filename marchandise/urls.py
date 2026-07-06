from django.urls import path
from . import views

app_name = 'marchandise'

urlpatterns = [
    path('', views.liste_lots, name='liste_lots'),
    path('lot/<int:pk>/', views.detail_lot, name='detail_lot'),
    path('reception/', views.reception_lot, name='reception_lot'),
    path('affecter/', views.affecter_superviseur, name='affecter_superviseur'),
    path('historique/', views.historique_affectations, name='historique_affectations'),
]
