from django.urls import path

from  direction.views import ( 
                                
                                ProductListView, ProductDetailView,ProductListPartialView,
                                AnalyseFournisseursView,DetailFournisseurView,ToutesLesVentesView,
                                ExportVentesExcelView, ExportVentesPDFView
                                
                              )


urlpatterns = [
    
    path('direction/produits/', ProductListView.as_view(), name='product_list'),
    path('direction/produits/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('direction/produits/table/', ProductListPartialView.as_view(), name='product_list_partial'),

    
    # Liste des fournisseurs
    path('direction/fournisseurs/liste/', 
         AnalyseFournisseursView.as_view(), 
         name='liste_fournisseurs_direction'),
    
    # Détail d'un fournisseur
    path('direction/fournisseurs/<int:pk>/detail/', 
         DetailFournisseurView.as_view(), 
         name='detail_fournisseur_direction'),
    
     path('direction/ventes', ToutesLesVentesView.as_view(), name='toutes_les_ventes'),  


    # EXPORTS
    path("direction/ventes/export/excel/", ExportVentesExcelView.as_view(), name="export_ventes_excel"),
    path("direction/ventes/export/pdf/", ExportVentesPDFView.as_view(), name="export_ventes_pdf"),


]


