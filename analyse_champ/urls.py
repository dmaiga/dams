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
]