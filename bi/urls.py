from django.urls import path

from bi import views

app_name = "bi"

urlpatterns = [
    path("", views.dashboard_sante, name="sommaire"),
    path("sante/", views.dashboard_sante, name="sante"),
    path("produits/", views.dashboard_produits, name="produits"),
    path("agents/", views.dashboard_agents, name="agents"),
    path(
        "agents/export/excel/",
        views.export_agents_sous_objectif_excel,
        name="export_agents_sous_objectif_excel",
    ),
    path(
        "agents/export/pdf/",
        views.export_agents_sous_objectif_pdf,
        name="export_agents_sous_objectif_pdf",
    ),
    path("agents/<int:agent_id>/", views.dashboard_agent_detail, name="agent_detail"),
    path("agents/equipe/<int:superviseur_id>/", views.dashboard_superviseur_detail, name="superviseur_detail"),
    path("depenses/", views.dashboard_depenses, name="depenses"),
    path("stock/", views.dashboard_stock, name="stock"),
]
