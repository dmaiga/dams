from django.urls import path

from surveillance.views.dashboard import (
    DashboardSurveillanceView
)
from surveillance.views.kg_vendu import (
    ListeKgVenduView,
)
from surveillance.views.superviseur import (
    DetailSuperviseurView
)
from surveillance.views.produits import (
    DetailProduitView
)
from surveillance.views.prix import (
    SurveillancePrixView,DetailPrixView
)
from surveillance.views.stock_rotation import (
    StockRotationView, RotationLenteListView, StockDormantListView
)


urlpatterns = [

    path( "",DashboardSurveillanceView.as_view(), name="dashboard_surveillance"),
    path( "kg-vendu/",ListeKgVenduView.as_view(), name="liste_kg_vendu" ),
    path( "superviseur/<int:pk>/",DetailSuperviseurView.as_view(), name="detail_superviseur" ),
    path( "produit/<int:pk>/", DetailProduitView.as_view(),name="detail_produit"),
    path( "prix/",SurveillancePrixView.as_view(),name="surveillance_prix"),
    path( "prix/<int:lot_id>/",DetailPrixView.as_view(),name="detail_prix" ),
    path( "stock-rotation/",StockRotationView.as_view(),name="stock_rotation" ),
    path( "stock-rotation/rotation-lente/",RotationLenteListView.as_view(),name="rotation_lente" ),
    path( "stock-rotation/stock-dormant/",StockDormantListView.as_view(),name="stock_dormant" ),

]