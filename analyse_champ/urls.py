from django.urls import path
from analyse_champ.views import *


urlpatterns = [

    path(
        'agros/dashboard',
        dashboard_view,
        name='agro_dashboard'
    ),

    path('agros/operations/',
        operation_list_view,
        name='agro_operation_list'
    ),
    path(
    'agros/operations/<int:pk>/',
    operation_detail_view,
    name='agro_operation_detail'
),

    path(
        'agros/products/',
        product_list_view,
        name='agro_product_list'
    ),

    path(
        'agros/products/<int:pk>/',
        product_detail_view,
        name='agro_product_detail'
    ),

    path(
        'agros/agents/',
        agent_list_view,
        name='agro_agent_list'
    ),
    path(
        'agros/rapports/',
        rapport_list_view,
        name='direction_rapport_list'
    ),

    path(
        'agros/rapports/<int:pk>/',
        rapport_detail_view,
        name='direction_rapport_detail'
    ),

    path(
        'agros/cultures/',
        fiche_list_view,
        name='agro_culture_list'
    ),
    path(
        'agros/cultures/rapports/',
        rapports_culture_list_view,
        name='agro_culture_rapports'
    ),
    path(
        'agros/cultures/connaissances/',
        connaissances_view,
        name='agro_culture_connaissances'
    ),
    path(
        'agros/cultures/<int:pk>/',
        fiche_detail_view,
        name='agro_culture_detail'
    ),
]