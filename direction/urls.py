from django.urls import path

from core import views
from direction import views as views_direction
from direction.views import ( 
                                
                                DashboardView,AgentDetailView,SuperviseurListView,
                                AgentDashboardView,AgentTerrainListView,
                               ProductListView, ProductDetailView,
                                AnalyseFournisseursView,DetailFournisseurView,ToutesLesVentesView,
                                ExportVentesExcelView, ExportVentesPDFView,   
                                liste_paiements_fournisseur,
                                creer_paiement_fournisseur,
                                modifier_paiement_fournisseur,
                                supprimer_paiement_fournisseur,
                                restaurer_paiement_fournisseur,
                                detail_paiement_fournisseur, 
                                 liste_clotures,apercu_cloture,cloturer_periode,                                                           
                              )


urlpatterns = [
        path('direction/dashboard/', DashboardView.as_view(), name='dashboard'),
       
    path('direction/agents/', AgentDashboardView.as_view(), name='agent_dashboard'),
    path('direction/agents/superviseurs/', SuperviseurListView.as_view(), name='superviseur_list'),
    path('direction/agents/terrain/', AgentTerrainListView.as_view(), name='agent_terrain_list'),
    path('direction/agents/<int:pk>/', AgentDetailView.as_view(), name='agent_detail'),
    
    path('direction/produits/', ProductListView.as_view(), name='product_list'),
    path('direction/produits/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
   
    
    # Liste des fournisseurs
    path('direction/fournisseurs/liste/', 
         AnalyseFournisseursView.as_view(), 
         name='liste_fournisseurs_direction'),
    
    # Détail d'un fournisseur
    path('direction/fournisseurs/<int:pk>/detail/', 
         DetailFournisseurView.as_view(), 
         name='detail_fournisseur_direction'),
    
    path('fournisseurs/<int:fournisseur_id>/paiements/', 
         liste_paiements_fournisseur, 
         name='liste_paiements_fournisseur'),
    
    path('fournisseurs/<int:fournisseur_id>/paiements/nouveau/', 
         creer_paiement_fournisseur, 
         name='creer_paiement_fournisseur'),
    
    path('paiements/<int:paiement_id>/modifier/', 
         modifier_paiement_fournisseur, 
         name='modifier_paiement_fournisseur'),
    
    path('paiements/<int:paiement_id>/supprimer/', 
         supprimer_paiement_fournisseur, 
         name='supprimer_paiement_fournisseur'),
    
    path('paiements/<int:paiement_id>/restaurer/', 
         restaurer_paiement_fournisseur, 
         name='restaurer_paiement_fournisseur'),
    
    path('paiements/<int:paiement_id>/', 
         detail_paiement_fournisseur, 
         name='detail_paiement_fournisseur'),
    
     path('direction/ventes', ToutesLesVentesView.as_view(), name='toutes_les_ventes'),  
    # Factures fournisseurs
    path('direction/factures/', views_direction.liste_factures_fournisseurs, name='factures_fournisseurs_direction'),
    
    # Versements bancaires
    path('direction/versements/', views_direction.liste_versements_direction, name='versements_direction'),
    path('direction/versements/<int:versement_id>/', views_direction.detail_versement_direction, name='detail_versement_direction'),
    
    # Rapports
    path('analyse-financiere/', views_direction.analyse_financiere_direction, name='analyse_financiere_direction'),
    # EXPORTS
    path("direction/ventes/export/excel/", ExportVentesExcelView.as_view(), name="export_ventes_excel"),
    path("direction/ventes/export/pdf/", ExportVentesPDFView.as_view(), name="export_ventes_pdf"),

          # =========================
         # CLÔTURES MENSUELLES
         # =========================

         # Liste de toutes les clôtures (multi-superviseurs)
         path(
             'clotures/',
             liste_clotures,
             name='liste_clotures'
         ),

         # Aperçu d’une clôture avant validation
         path(
             'clotures/<int:cloture_id>/apercu/',
             apercu_cloture,
             name='apercu_cloture'
         ),

         # Validation / clôture effective
         path(
             'clotures/<int:cloture_id>/cloturer/',
             cloturer_periode,
             name='cloturer_periode'
         ),

]


