from django.urls import path
from . import views, htmx_views

app_name = "direction"

urlpatterns = [
    path("", views.dashboard, name="dashboard_direction"),

    # HTMX endpoints
    path("kpis/", htmx_views.kpis, name="kpis"),
    path("stock/", htmx_views.stock, name="stock"),
    path("ventes/", htmx_views.ventes, name="ventes"),
    path("agents/", htmx_views.agents, name="agents"),
    path("dettes/", htmx_views.dettes, name="dettes"),
    path("depenses/", htmx_views.depenses, name="depenses"),
]
