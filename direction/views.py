from direction.services.product_analysis_service import ProductAnalysisService

from core.models import (
    Agent, Client, Vente, Produit, Facture,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,
    Recouvrement,VersementBancaire,VersementBancaire,RecuVersement
)



from django.views.generic import TemplateView, DetailView,ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator




class ProductListView(LoginRequiredMixin, ListView):
    template_name = 'core/analyses/produits/produit_liste.html'
    context_object_name = 'products_data'
    paginate_by = 20
    
    def get_queryset(self):
        supplier_id = self.request.GET.get('fournisseur')
        return ProductAnalysisService.get_products_by_supplier(supplier_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # KPI globaux
        context['kpis'] = ProductAnalysisService.get_product_kpis()
        
        # Liste des fournisseurs pour le filtre
        context['suppliers'] = ProductAnalysisService.get_suppliers_with_stats()
        
        # Fournisseur sélectionné
        selected_supplier_id = self.request.GET.get('fournisseur')
        if selected_supplier_id:
            try:
                context['selected_supplier'] = Fournisseur.objects.get(id=selected_supplier_id)
            except Fournisseur.DoesNotExist:
                context['selected_supplier'] = None
        
        # Paramètres de filtrage
        context['current_filters'] = {
            'fournisseur': selected_supplier_id
        }
        
        # Ventes par agent pour le fournisseur sélectionné
        if selected_supplier_id:
            context['ventes_par_agent'] = ProductAnalysisService.get_ventes_par_agent(selected_supplier_id)
        
        # Pagination manuelle
        products_data = self.get_queryset()
        paginator = Paginator(products_data, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['page_obj'] = page_obj
        context['products_data'] = page_obj.object_list
        context['is_paginated'] = page_obj.has_other_pages()
        
        return context
    
class ProductDetailView(LoginRequiredMixin, DetailView):
    template_name = 'core/analyses/produits/produit_detail.html'
    context_object_name = 'product_data'
    
    def get_object(self):
        product_id = self.kwargs.get('pk')
        supplier_id = self.request.GET.get('fournisseur')
        return ProductAnalysisService.get_product_detail(product_id, supplier_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['kpis'] = ProductAnalysisService.get_product_kpis()
        
        # Passer le fournisseur sélectionné si existant
        supplier_id = self.request.GET.get('fournisseur')
        if supplier_id:
            try:
                context['selected_supplier'] = Fournisseur.objects.get(id=supplier_id)
            except Fournisseur.DoesNotExist:
                context['selected_supplier'] = None
        
        return context
    
class ProductListPartialView(LoginRequiredMixin, ListView):
    template_name = "direction/analyses/produits/partials/produit_table.html"
    context_object_name = "products_data"
    paginate_by = 20

    def get_queryset(self):
        supplier_id = self.request.GET.get("fournisseur")
        return ProductAnalysisService.get_products_by_supplier(supplier_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # conserver les filtres pour la pagination
        context["current_filters"] = {
            "fournisseur": self.request.GET.get("fournisseur")
        }

        return context
