from django.urls import path

from bi import views

app_name = "bi"

urlpatterns = [
    path("", views.sommaire, name="sommaire"),
    path("sante/", views.dashboard_sante, name="sante"),
    path("produits/", views.dashboard_produits, name="produits"),
    path("superviseurs/", views.dashboard_superviseurs, name="superviseurs"),
    path("agents/", views.dashboard_agents, name="agents"),
    path("stock/", views.dashboard_stock, name="stock"),
]
