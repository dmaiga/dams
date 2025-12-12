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
# direction/views/fournisseur_views.py
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum, Q, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
from django.http import JsonResponse, HttpResponse
from django.views.generic import  View,ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from direction.services.fournisseur_service import FournisseurAnalyseService

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from direction.services.vente_analyses import VenteAnalyseService
from core.models import Vente
from direction.services.vente_export import VenteExportService
from datetime import datetime

#Product

class ProductListView(LoginRequiredMixin, ListView):
    """
    View to display a paginated list of products with filtering options by supplier.
    Provides additional context data such as KPIs and sales statistics.
    """

    template_name = 'core/analyses/produits/produit_liste.html'
    context_object_name = 'products_data'
    paginate_by = 20

    def get_queryset(self):
        """
        Retrieve the list of products filtered by the selected supplier.

        Returns:
            QuerySet: A list of products filtered by supplier if provided.
        """
        supplier_id = self.request.GET.get('fournisseur')
        return ProductAnalysisService.get_products_by_supplier(supplier_id)

    def get_context_data(self, **kwargs):
        """
        Add additional context data to the template, including KPIs, suppliers, and sales statistics.

        Args:
            **kwargs: Additional keyword arguments passed to the context.

        Returns:
            dict: The context data for the template.
        """
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

#Fournisseur


class AnalyseFournisseursView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vue pour l'analyse des fournisseurs"""
    
    def test_func(self):
        return self.request.user.agent.est_direction or self.request.user.agent.est_superviseur
    
    def get(self, request):
        # Récupération des paramètres de filtre
        periode_type = request.GET.get('periode', 'annee')
        annee = request.GET.get('annee', timezone.now().year)
        mois = request.GET.get('mois', timezone.now().month)
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        
        # Application du filtre selon le type
        if periode_type == 'annee':
            analyse_data = FournisseurAnalyseService.get_analyse_annuelle(int(annee))
            periode_label = f"Année {annee}"
        
        elif periode_type == 'mois':
            analyse_data = FournisseurAnalyseService.get_analyse_mensuelle(int(mois), int(annee))
            periode_label = f"{mois}/{annee}"
        
        elif periode_type == 'personnalise' and date_debut and date_fin:
            date_debut_obj = timezone.make_aware(datetime.strptime(date_debut, '%Y-%m-%d'))
            date_fin_obj = timezone.make_aware(datetime.strptime(date_fin, '%Y-%m-%d'))
            analyse_data = FournisseurAnalyseService.get_analyse_periode(date_debut_obj, date_fin_obj)
            periode_label = f"Du {date_debut} au {date_fin}"
        
        else:
            # Par défaut: année en cours
            analyse_data = FournisseurAnalyseService.get_analyse_annuelle()
            periode_label = f"Année {timezone.now().year}"
        
        context = {
            'analyse_data': analyse_data['analyse_data'],
            'kpi_globaux': analyse_data['kpi_globaux'],
            'periode_label': periode_label,
            'periode_type': periode_type,
            'annees': range(timezone.now().year - 5, timezone.now().year + 1),
            'mois': [
                (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
                (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
                (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
            ],
            'current_year': timezone.now().year,
            'current_month': timezone.now().month,
        }
        
        return render(
                        request, 
                        'direction/analyses/fournisseurs/liste.html',
                         context
                    )

class DetailFournisseurView(LoginRequiredMixin, UserPassesTestMixin, View):

    """Vue détaillée d'un fournisseur"""
    
    def test_func(self):
        return self.request.user.agent.est_direction or self.request.user.agent.est_superviseur
    
    def get(self, request, pk):
        # Récupération des paramètres de filtre
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        
        # Conversion des dates si fournies
        date_debut_obj = None
        date_fin_obj = None
        
        if date_debut:
            date_debut_obj = timezone.make_aware(datetime.strptime(date_debut, '%Y-%m-%d'))
        if date_fin:
            date_fin_obj = timezone.make_aware(datetime.strptime(date_fin, '%Y-%m-%d'))
        
        # Récupération des données
        detail_data = FournisseurAnalyseService.get_detail_fournisseur(
            pk, date_debut_obj, date_fin_obj
        )
        
        context = {
            **detail_data,
            'date_debut': date_debut,
            'date_fin': date_fin,
        }
        
        return render(
                        request,
                         'direction/analyses/fournisseurs/detail.html',
                         context
                    )
    

# views.py
from datetime import datetime
from decimal import Decimal

class ToutesLesVentesView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Vente
    template_name = "direction/analyses/ventes/liste_ventes_admin.html"
    context_object_name = "ventes"
  
    def test_func(self):
        return (
            self.request.user.agent.est_direction
            or self.request.user.agent.est_superviseur
        )

    def get_queryset(self):
        params = self.request.GET
        periode = params.get("periode", "annee")

        # 1) période
        date_debut, date_fin = VenteAnalyseService.normalize_period(periode, params)

        # 2) filtres agent + type
        agent_id = params.get("agent")
        type_vente = params.get("type")
        produit_id = params.get("produit") 

        # 3) appel service
        qs = VenteAnalyseService.filter_ventes(
            date_debut=date_debut,
            date_fin=date_fin,
            agent_id=agent_id,
            type_vente=type_vente,
            produit_id=produit_id
        )

        self.filtered_queryset = qs
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.periode = periode

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        params = self.request.GET
        ventes_filtrees = self.filtered_queryset
        page_obj = context["ventes"]

        # --------------------------
        # Stats globales (toutes ventes filtrées)
        # --------------------------
        stats = VenteAnalyseService.compute_stats(ventes_filtrees)
        top_agents = VenteAnalyseService.compute_top_agents(ventes_filtrees)
        agents_list = VenteAnalyseService.get_agents_list()

        # --------------------------
        # Marge pour la page ACTIVE SEULEMENT
        # --------------------------
        for vente in page_obj:
            prix_achat = getattr(
                vente.detail_distribution.lot, 
                'prix_achat_unitaire', 
                Decimal('0.00')
            )

            cout_total = vente.quantite * prix_achat
            marge = vente.total_vente - cout_total
            taux_marge = (marge / vente.total_vente * 100) if vente.total_vente > 0 else 0

            vente.marge = marge
            vente.taux_marge = taux_marge
            
            # Ajouter le nom complet du stagiaire si présent
            if vente.stagiaire:
                vente.stagiaire_nom_complet = vente.stagiaire.full_name
            else:
                vente.stagiaire_nom_complet = None

        # --------------------------
        # Mise en contexte
        # --------------------------
        current_year = datetime.now().year
        months = [
            (1, 'Jan'), (2, 'Fév'), (3, 'Mar'), (4, 'Avr'),
            (5, 'Mai'), (6, 'Juin'), (7, 'Juil'), (8, 'Août'),
            (9, 'Sep'), (10, 'Oct'), (11, 'Nov'), (12, 'Déc')
        ]

        context.update({
            # KPI globaux
            "total_ca": stats["total_ca"],
            "total_marge": stats["total_marge"],
            "taux_marge": round(stats["taux_marge"], 1),
            "ventes_gros": stats["ventes_gros"],
            "ventes_detail": stats["ventes_detail"],
            "total_quantite": stats["total_quantite"],
            "clients_count": stats["clients_count"],
            "agents_count": stats["agents_count"],


            # Autres
            "top_agents": top_agents,
            "agents_list": agents_list,
            "years": list(range(current_year - 2, current_year + 3)),
            "months": months,
            "current_year": current_year,
            "current_month": datetime.now().month,
            "periode": self.periode,
            "date_debut": self.date_debut,
            "date_fin": self.date_fin,
            "produits_list": Produit.objects.all().order_by("nom"),
        })

        return context

class ExportVentesExcelView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Vente

    def test_func(self):
        return (
            self.request.user.agent.est_direction
            or self.request.user.agent.est_superviseur
        )

    def get(self, request, *args, **kwargs):
        params = request.GET
        periode = params.get("periode", "annee")

        # 1) Dates
        date_debut, date_fin = VenteAnalyseService.normalize_period(periode, params)

        # 2) Queryset
        ventes = VenteAnalyseService.filter_ventes(
            date_debut, date_fin,
            agent_id=params.get("agent"),
            type_vente=params.get("type"),
        )

        # 3) Génération Excel
        buffer = VenteExportService.export_excel(ventes, date_debut, date_fin)

        # 4) Réponse HTTP
        response = HttpResponse(
            buffer,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f"attachment; filename=ventes_{date_debut.date()}_{date_fin.date()}.xlsx"
        return response


class ExportVentesPDFView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Vente

    def test_func(self):
        return (
            self.request.user.agent.est_direction
            or self.request.user.agent.est_superviseur
        )

    def get(self, request, *args, **kwargs):
        params = request.GET
        periode = params.get("periode", "annee")

        # 1) Dates
        date_debut, date_fin = VenteAnalyseService.normalize_period(periode, params)

        # 2) Queryset
        ventes = VenteAnalyseService.filter_ventes(
            date_debut, date_fin,
            agent_id=params.get("agent"),
            type_vente=params.get("type"),
        )

        # 3) Génération PDF
        buffer = VenteExportService.export_pdf(ventes, date_debut, date_fin)

        # 4) Réponse HTTP
        response = HttpResponse(
            buffer,
            content_type="application/pdf"
        )
        response["Content-Disposition"] = f"attachment; filename=ventes_{date_debut.date()}_{date_fin.date()}.pdf"
        return response
