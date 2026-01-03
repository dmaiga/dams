# urls.py
from django.urls import path
from . import views

urlpatterns = [
#tableau_de_bord
   path('tableau-de-bord/superviseur/', views.tableau_de_bord_superviseur, name='tableau_de_bord_superviseur'),
     path('dashboard/', views.tableau_de_bord_rot, name='dashboard_rot'),
]