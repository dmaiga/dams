from django.urls import path

from  direction.views import ( 
                      ProductListView, ProductDetailView,ProductListPartialView
                     
                     )

urlpatterns = [
    
    path('direction/produits/', ProductListView.as_view(), name='product_list'),
    path('direction/produits/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('direction/produits/table/', ProductListPartialView.as_view(), name='product_list_partial'),
]


