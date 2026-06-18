from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar
import json

from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone



from datetime import date, timedelta
from django.contrib.auth.decorators import login_required

from direction.services.analyse_financiere_service import (
    AnalyseFinanciereDirectionService
)
from core.models import Agent

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Avg, Q, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View, TemplateView, ListView, DetailView
from django.db.models.functions import Concat
from django.db.models import Value, CharField

from django.core.paginator import Paginator

from core.models import (
    Agent, Client, Produit, Vente,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,
    Fournisseur, PaiementFournisseur,
    FactureLotEntrepot, MouvementStock,
    JournalModificationDistribution,
    Recouvrement, VersementBancaire, RecuVersement,
    Depense,ClotureMensuelle
)
from django.db.models import OuterRef, Subquery, DateTimeField

from core.forms import RapportDettesForm, PaiementFournisseurForm
from agents.forms import (
                          
                            
                            DirectionAgentCreationForm,
                            RotSupervisorCreationForm,
                            SupervisorTerrainAgentCreationForm
                            )

from direction.services.product_analysis_service import ProductAnalysisService


from direction.services.agent_dashboard_service import DashboardAgentAnalysisService
from direction.services.agent_analysis_service import AgentAnalysisService

from direction.services.agent_supervisseur_detail_analyse import SuperviseurAgentsService
from direction.services.agent_supervisseur_liste_analyse import SuperviseurAnalysisService

from direction.services.agent_terrain_service_liste import AgentTerrainListeService
from direction.services.agent_detail_service import AgentDetailService

from direction.services.fournisseur_service import FournisseurAnalyseService
from direction.services.vente_analyses import VenteAnalyseService
from direction.services.vente_export import VenteExportService
from direction.services.dashboard_service import DashboardService
from direction.services.cloture_service import calculer_solde_periode

from direction.services.analyse_operationnelle_service import AnalyseOperationnelleService

# core/views/dashboard.py

from direction.services.DashboardSnapshotService import DashboardSnapshotService

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'direction/analyses/dashboards/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        periode_type = self.request.GET.get('periode', 'annee')
        annee = int(self.request.GET.get('annee', timezone.now().year))
        mois = self.request.GET.get('mois')

        if mois:
            mois = int(mois)

        snapshot = DashboardSnapshotService.get_snapshot(
            periode_type,
            annee,
            mois,
            self.request.user
        )

        context.update(snapshot)

        # Mois disponibles avec leurs noms
        mois_liste = [
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
            (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
            (7, 'Juillet'), (8, 'Août'), (9, 'Septembre'),
            (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
        ]

        # Années disponibles (année en cours et 2 années précédentes)
        today = timezone.now()
        annees_disponibles = list(range(today.year - 2, today.year + 1))

        context.update({
            "annee_selectionnee": annee,
            "mois_selectionne": mois,
            "periode_selectionnee": periode_type,
            "mois_liste": mois_liste,
            "annees_disponibles": annees_disponibles,
        })

        return context


#AGENT

class AgentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'direction/analyses/agents/agent_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        snapshot = DashboardAgentAnalysisService.get_agents_dashboard_snapshot()

        context.update(snapshot)

        return context

class SuperviseurListView(LoginRequiredMixin, TemplateView):
    template_name = 'direction/analyses/agents/superviseur_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 📊 Situation financière ACTUELLE (post-clôture)
        context["superviseurs"] = (
            SuperviseurAnalysisService.get_superviseurs_finance()
        )

        context["rots"] = (
            SuperviseurAnalysisService.get_rots_finance()
        )

        return context

def SuperviseurDetail(request, pk):
    superviseur = get_object_or_404(Agent, pk=pk, type_agent='entrepot')
    periode = SuperviseurAgentsService.resolve_period(request)

    agents, totals = SuperviseurAgentsService.get_agents_ventes(
        superviseur,
        periode["date_debut"],
        periode["date_fin"]
    )

    flux = SuperviseurAgentsService.get_flux(
        superviseur,
        periode["date_debut"],
        periode["date_fin"]
    )

    matrice = SuperviseurAgentsService.get_matrice_distribution(
        superviseur,
        periode["date_debut"],
        periode["date_fin"]
    )

    kpis = SuperviseurAgentsService.build_kpis(totals, flux)

    return render(
        request,
        "direction/analyses/agents/superviseur_detail.html",
        {
            "superviseur": superviseur,
            "agents": agents,
            "flux": flux,
            "kpis": kpis,
            "matrice": matrice,
            **periode,
        }
    ) 

class AgentTerrainListView(LoginRequiredMixin, TemplateView):
    template_name = "direction/analyses/agents/agent_terrain_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ----------------------------
        # PÉRIODE (AGENTS – hebdo par défaut)
        # ----------------------------
        periode_data = AgentTerrainListeService.resolve_period(self.request)
        date_debut = periode_data["date_debut"]
        date_fin = periode_data["date_fin"]

        # ----------------------------
        # FILTRES
        # ----------------------------
        type_agent = self.request.GET.get("type_agent")  # terrain | agent_gros | None
        superviseur_id = self.request.GET.get("superviseur")

        superviseur = None
        if superviseur_id:
            superviseur = get_object_or_404(Agent, pk=superviseur_id)

        # ----------------------------
        # SERVICE MÉTIER
        # ----------------------------
        agents = AgentTerrainListeService.get_agents_liste(
            date_debut=date_debut,
            date_fin=date_fin,
            superviseur=superviseur,
            type_agent=type_agent,
        )

        # ----------------------------
        # CONTEXTE
        # ----------------------------
        context.update({
            "agents": agents,

            # période
            "periode": periode_data["periode"],
            "date_debut": date_debut,
            "date_fin": date_fin,

            # filtres
            "current_type_agent": type_agent,
            "current_superviseur": superviseur_id,

            # listes
            "superviseurs": Agent.objects.filter(
                type_agent="entrepot",
                est_actif=True
            ),
        })

        return context

class AgentDetailView(LoginRequiredMixin, DetailView):
    model = Agent
    template_name = "direction/analyses/agents/agent_detail.html"
    context_object_name = "agent"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        agent = self.object

        # ----------------------------
        # PÉRIODE (hebdo par défaut)
        # ----------------------------
        periode_data = AgentDetailService.resolve_period(self.request)
        date_debut = periode_data["date_debut"]
        date_fin = periode_data["date_fin"]

        # ----------------------------
        # SERVICE MÉTIER
        # ----------------------------
        analysis = AgentDetailService.get_agent_detail(
            agent=agent,
            date_debut=date_debut,
            date_fin=date_fin,
        )

        # ----------------------------
        # CONTEXTE
        # ----------------------------
        context.update(analysis)
        context.update({
            "periode": periode_data["periode"],
            "date_debut": date_debut,
            "date_fin": date_fin,
        })

        return context

def RotDetailView(request, pk):
    rot = get_object_or_404(Agent, pk=pk, type_agent='rot')

    periode = AgentAnalysisService.resolve_period(request)
    data = AgentAnalysisService.get_rot_detail(
        rot,
        periode["date_debut"],
        periode["date_fin"]
    )

    return render(request, "direction/analyses/agents/rot_detail.html", {
        **data,
        **periode,
    })



@login_required
def analyse_operationnelle(request):
    # 🔹 paramètres
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    agent_id = request.GET.get('agent')
    produit_id = request.GET.get('produit')

    if not date_debut or not date_fin:
        date_fin = date.today()
        date_debut = date(date_fin.year, 1, 1)
    
    resultats = AnalyseOperationnelleService.analyser(
        date_debut=date_debut,
        date_fin=date_fin,
        agent_id=agent_id,
        produit_id=produit_id
    )

    context = {
        **resultats,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'agents': Agent.objects.filter(type_agent__in=['terrain', 'agent_gros']),
        'produits': Produit.objects.all(),
    }

    return render(request, 'direction/analyses/agents/analyse_operationnelle.html', context)

#Product

class ProductListView(LoginRequiredMixin, ListView):
    """
    View to display products analysis by PERIOD.
    Pivot: PRODUIT (not supplier)
    Allows answering: "How much invested in February on garlic?"
    """

    template_name = 'direction/analyses/produits/produit_liste.html'
    context_object_name = 'products_data'
    paginate_by = 20

    def get_date_range(self):
        """Extract and validate period parameters"""
        periode = self.request.GET.get('periode', 'mois_courant')
        today = timezone.now()

        if periode == 'mois_courant':
            date_debut = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            dernier_jour = calendar.monthrange(today.year, today.month)[1]
            date_fin = today.replace(day=dernier_jour, hour=23, minute=59, second=59, microsecond=999999)
        
        elif periode == 'mois_custom':
            mois = int(self.request.GET.get('mois', today.month))
            annee = int(self.request.GET.get('annee', today.year))
            date_debut = datetime(annee, mois, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
            dernier_jour = calendar.monthrange(annee, mois)[1]
            date_fin = datetime(annee, mois, dernier_jour, 23, 59, 59, tzinfo=timezone.get_current_timezone())
        
        elif periode == 'annee_courant':
            date_debut = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            date_fin = today.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        
        elif periode == 'custom':
            date_debut_str = self.request.GET.get('date_debut')
            date_fin_str = self.request.GET.get('date_fin')
            try:
                from django.utils.dateparse import parse_datetime
                date_debut = parse_datetime(f"{date_debut_str}T00:00:00") or today.replace(day=1)
                date_fin = parse_datetime(f"{date_fin_str}T23:59:59") or today
            except:
                date_debut = today.replace(day=1)
                date_fin = today
        
        else:  # default: 30 derniers jours
            date_fin = today
            date_debut = today - timedelta(days=30)

        return date_debut, date_fin, periode

    def get_queryset(self):
        """Get products for the selected period"""
        date_debut, date_fin, periode = self.get_date_range()
        produit_id = self.request.GET.get('produit')
        
        # Call new service method with period filtering
        return ProductAnalysisService.get_products_by_period(
            date_debut=date_debut,
            date_fin=date_fin,
            produit_id=produit_id
        )

    def get_context_data(self, **kwargs):
        """Add period filters and KPIs to template"""
        context = super().get_context_data(**kwargs)

        date_debut, date_fin, periode = self.get_date_range()

        # KPI globaux
        context['kpis'] = ProductAnalysisService.get_product_kpis()

        # Filtres de période
        context['periode_selectionnee'] = periode
        context['date_debut'] = date_debut
        context['date_fin'] = date_fin

        # Listes pour les filtres
        mois_liste = [
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
            (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
            (7, 'Juillet'), (8, 'Août'), (9, 'Septembre'),
            (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
        ]
        today = timezone.now()
        annees_disponibles = list(range(today.year - 2, today.year + 1))

        context.update({
            'mois_liste': mois_liste,
            'annees_disponibles': annees_disponibles,
            'mois_courant': today.month,
            'annee_courant': today.year,
        })

        # Produits sélectionné
        produit_id = self.request.GET.get('produit')
        if produit_id:
            try:
                context['produit_detail'] = Produit.objects.get(id=produit_id)
            except Produit.DoesNotExist:
                context['produit_detail'] = None

        # STATS TOTALES POUR LA PÉRIODE
        products = self.get_queryset()
        stats_periode = {
            'total_investi': sum(p['montant_investi'] for p in products),
            'total_ca': sum(p['total_ca'] for p in products),
            'total_marge': sum(p['marge_totale'] for p in products),
            'quantite_recue': sum(p['quantite_recue'] for p in products),
            'quantite_vendue': sum(p['quantite_vendue'] for p in products),
        }
        stats_periode['taux_marge_periode'] = float(
            (stats_periode['total_marge'] / stats_periode['total_ca'] * 100)
            if stats_periode['total_ca'] > 0 else 0
        )
        context['stats_periode'] = stats_periode

        # Pagination
        paginator = Paginator(products, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        context['products_data'] = page_obj.object_list
        context['is_paginated'] = page_obj.has_other_pages()

        return context
    
class ProductDetailView(LoginRequiredMixin, DetailView):
    template_name = 'direction/analyses/produits/produit_detail.html'
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
    

#ventes

class ToutesLesVentesView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Vente
    template_name = "direction/analyses/ventes/liste_ventes_admin.html"
    context_object_name = "ventes"
    paginate_by = 25  

    # ------------------------------------------------------------------
    # CACHE USER + AGENT (ANTI 1000 REQUÊTES)
    # ------------------------------------------------------------------
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.user = request.user
        self.agent = getattr(request.user, "agent", None)

    def test_func(self):
        return self.agent and (
            self.agent.est_direction or self.agent.est_superviseur
        )

    # ------------------------------------------------------------------
    # QUERYSET UNIQUE, OPTIMISÉ, AVEC ANNOTATIONS SQL
    # ------------------------------------------------------------------
    from django.db.models import F, DecimalField, ExpressionWrapper

    def get_queryset(self):
        params = self.request.GET
        periode = params.get("periode", "annee")

        date_debut, date_fin = VenteAnalyseService.normalize_period(periode, params)

        agent_id = params.get("agent")
        type_vente = params.get("type")
        produit_id = params.get("produit")
        lot_id = params.get("lot")
        superviseur_id = params.get("superviseur")

        qs = VenteAnalyseService.filter_ventes(
            date_debut=date_debut,
            date_fin=date_fin,
            agent_id=agent_id,
            type_vente=type_vente,
            produit_id=produit_id,
            lot_id=lot_id,
            superviseur_id=superviseur_id
        )

        dernier_recouvrement = Recouvrement.objects.filter(
            vente_id=OuterRef("pk")
        ).order_by("-date_recouvrement")

        qs = qs.annotate(
            total_vente_sql=ExpressionWrapper(
                F("quantite") * F("prix_vente_unitaire"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            cout_total=ExpressionWrapper(
                F("quantite") * F("detail_distribution__lot__prix_achat_unitaire"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            marge=ExpressionWrapper(
                (F("quantite") * F("prix_vente_unitaire")) -
                (F("quantite") * F("detail_distribution__lot__prix_achat_unitaire")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            date_recouvrement=Subquery(
                dernier_recouvrement.values("date_recouvrement")[:1],
                output_field=DateTimeField()
            ),
            stagiaire_nom_complet=Concat(
                F("stagiaire__user__first_name"),
                Value(" "),
                F("stagiaire__user__last_name"),
                output_field=CharField()
            )
        )

        self.filtered_queryset = qs
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.periode = periode

        return qs

    # ------------------------------------------------------------------
    # CONTEXTE — ZÉRO REQUÊTE EN BOUCLE
    # ------------------------------------------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ventes_qs = self.filtered_queryset

        stats = VenteAnalyseService.compute_stats(ventes_qs)
        top_agents = VenteAnalyseService.compute_top_agents(ventes_qs)
        agents_list = VenteAnalyseService.get_agents_list()
        superviseurs_list = (
            VenteAnalyseService
            .get_superviseurs_list()
        )
        current_year = timezone.now().year
        months = [
            (1, 'Jan'), (2, 'Fév'), (3, 'Mar'), (4, 'Avr'),
            (5, 'Mai'), (6, 'Juin'), (7, 'Juil'), (8, 'Août'),
            (9, 'Sep'), (10, 'Oct'), (11, 'Nov'), (12, 'Déc')
        ]

        context.update({
            "total_ca": stats["total_ca"],
            "total_marge": stats["total_marge"],
            "taux_marge": round(stats["taux_marge"], 1),
            "ventes_gros": stats["ventes_gros"],
            "ventes_detail": stats["ventes_detail"],
            "total_quantite": stats["total_quantite"],
            "clients_count": stats["clients_count"],
            "agents_count": stats["agents_count"],

            "top_agents": top_agents,
            "agents_list": agents_list,
            "superviseurs_list": superviseurs_list,
            "produits_list": Produit.objects.only("id", "nom").order_by("nom"),
            "lots_list": LotEntrepot.objects.select_related("produit")
                        .order_by("-date_reception"),

            "years": list(range(current_year - 2, current_year + 3)),
            "months": months,
            "current_year": current_year,
            "current_month": timezone.now().month,
            "periode": self.periode,
            "date_debut": self.date_debut,
            "date_fin": self.date_fin,
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

        # 2) ✅ EXACT SAME FILTERS
        ventes = VenteAnalyseService.filter_ventes(
            date_debut=date_debut,
            date_fin=date_fin,
            agent_id=params.get("agent"),
            type_vente=params.get("type"),
            produit_id=params.get("produit"),
            lot_id=params.get("lot"),
            superviseur_id=params.get("superviseur"),   
        )

        # 3) Export
        buffer = VenteExportService.export_excel(ventes, date_debut, date_fin)

        response = HttpResponse(
            buffer,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            f"attachment; filename=ventes_{date_debut.date()}_{date_fin.date()}.xlsx"
        )

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
            date_debut=date_debut,
            date_fin=date_fin,
            agent_id=params.get("agent"),
            type_vente=params.get("type"),
            produit_id=params.get("produit"),
            lot_id=params.get("lot"),
            superviseur_id=params.get("superviseur"),   
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



#factures
@login_required
def dashboard_justificatif(request):
    """Tableau de bord direction - Vue d'ensemble"""

    
    # Statistiques financières
    factures_fournisseurs = LotEntrepot.objects.exclude(facture='')
    total_factures = sum(f.valeur_stock_initiale for f in factures_fournisseurs if f.valeur_stock_initiale)
    
    versements = VersementBancaire.objects.all()
    total_versements = sum(v.montant_total for v in versements)
    
    # Statistiques superviseurs
    superviseurs = Agent.objects.filter(type_agent='entrepot')
    
    context = {
        'total_factures': total_factures,
        'total_versements': total_versements,
        'superviseurs': superviseurs,
        'factures_recentes': factures_fournisseurs[:5],
        'versements_recents': versements[:5],
    }
    
    return render(request, 'direction/factures/justificatif.html', context)


@login_required
def liste_factures_fournisseurs(request):
    """Liste complète des factures fournisseurs (pour direction)"""
    
    # Récupérer toutes les factures avec les informations du lot
    factures = FactureLotEntrepot.objects.select_related(
        'lot', 
        'lot__fournisseur', 
        'lot__produit'
    ).order_by('-date_upload')
    
    # Filtrer par fournisseur (optionnel)
    fournisseur_id = request.GET.get('fournisseur')
    if fournisseur_id:
        factures = factures.filter(lot__fournisseur_id=fournisseur_id)
    
    # Filtrer par date (optionnel)
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    if date_debut:
        factures = factures.filter(date_upload__date__gte=date_debut)
    if date_fin:
        factures = factures.filter(date_upload__date__lte=date_fin)
    
    # Calculer les totaux
    total_montant_factures = factures.aggregate(
        total=Sum('montant')
    )['total'] or Decimal('0')
    
    # Calculer par fournisseur
    stats_fournisseurs = FactureLotEntrepot.objects.values(
        'lot__fournisseur__nom',
        'lot__fournisseur_id'
    ).annotate(
        total_factures=Sum('montant'),
        nombre_factures=Count('id')
    ).order_by('-total_factures')
    
    # Liste des fournisseurs pour le filtre
    fournisseurs = Fournisseur.objects.all().order_by('nom')
    
    context = {
        'factures': factures,
        'total_montant_factures': total_montant_factures,
        'stats_fournisseurs': stats_fournisseurs,
        'fournisseurs': fournisseurs,
        'title': 'Factures Fournisseurs - Direction'
    }
    return render(request, 'direction/factures/liste_factures_fournisseurs.html', context)

@login_required
def liste_versements_direction(request):
    """Vue direction — analyse des VERSEMENTS uniquement"""

    versements = (
        VersementBancaire.objects
        .select_related(
            'effectue_par', 'effectue_par__user'
        )
        .prefetch_related('recus')
        .order_by('-date_versement_reelle')
    )

    filtres_actifs = {}

    # ========= FILTRE ROT =========
    rot_id = request.GET.get('rot')
    if rot_id:
        versements = versements.filter(effectue_par_id=rot_id)
        filtres_actifs['rot'] = rot_id

    # ========= FILTRE PERIODE =========
    periode = request.GET.get('periode')
    aujourd_hui = timezone.now().date()

    if periode == 'mois_courant':
        debut = aujourd_hui.replace(day=1)
        fin = (debut + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        versements = versements.filter(
            date_versement_reelle__range=(debut, fin)
        )
        filtres_actifs['periode'] = 'Mois en cours'

    elif periode == 'annee_courante':
        debut = aujourd_hui.replace(month=1, day=1)
        fin = aujourd_hui.replace(month=12, day=31)
        versements = versements.filter(
            date_versement_reelle__range=(debut, fin)
        )
        filtres_actifs['periode'] = 'Année en cours'

    elif periode == 'custom':
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        if date_debut and date_fin:
            versements = versements.filter(
                date_versement_reelle__gte=date_debut,
                date_versement_reelle__lte=date_fin
            )
            filtres_actifs['periode'] = 'Période personnalisée'
            filtres_actifs['date_debut'] = date_debut
            filtres_actifs['date_fin'] = date_fin

    # ========= FILTRE TYPE VERSEMENT =========
    type_versement = request.GET.get('type_versement')
    if type_versement and type_versement != 'tous':
        if type_versement == 'vente':
            versements = versements.filter(montant_vente__gt=0, montant_hors_vente=0)
        elif type_versement == 'hors_vente':
            versements = versements.filter(montant_hors_vente__gt=0, montant_vente=0)
        elif type_versement == 'mixte':
            versements = versements.filter(montant_vente__gt=0, montant_hors_vente__gt=0)
        filtres_actifs['type_versement'] = type_versement

    # ========= FILTRE REÇUS =========
    avec_recus = request.GET.get('avec_recus')
    if avec_recus in ('oui', 'non'):
        versements = versements.annotate(nb_recus=Count('recus'))
        versements = versements.filter(
            nb_recus__gt=0 if avec_recus == 'oui' else Q(nb_recus=0)
        )
        filtres_actifs['avec_recus'] = avec_recus

    # ========= STATS VERSEMENTS =========
    stats = versements.aggregate(
        total_vente=Sum('montant_vente'),
        total_hors_vente=Sum('montant_hors_vente'),
        nombre=Count('id'),
        moyenne_vente=Avg('montant_vente'),
        moyenne_hors_vente=Avg('montant_hors_vente'),
    )

    total_vente = stats['total_vente'] or Decimal('0.00')
    total_hors_vente = stats['total_hors_vente'] or Decimal('0.00')
    nombre_versements_filtres = versements.count()

    context = {
        'versements': versements,
        'nombre_versements_filtres': nombre_versements_filtres,
        # Stats
        'total_vente': total_vente,
        'total_hors_vente': total_hors_vente,
        'total_general': total_vente + total_hors_vente,
        'nombre_versements': stats['nombre'] or 0,

        # Filtres
        'filtres_actifs': filtres_actifs,
        'rots': Agent.objects.filter(type_agent='rot').select_related('user'),

        'periodes_disponibles': [
            ('', 'Sélectionner période'),
            ('mois_courant', 'Mois en cours'),
            ('annee_courante', 'Année en cours'),
            ('custom', 'Période personnalisée'),
        ],
        'types_versement': [
            ('tous', 'Tous'),
            ('vente', 'Vente'),
            ('hors_vente', 'Hors vente'),
            ('mixte', 'Mixte'),
        ],
        'options_recus': [
            ('', 'Peu importe'),
            ('oui', 'Avec reçus'),
            ('non', 'Sans reçus'),
        ],
    }

    return render(request, 'direction/factures/liste_versements.html', context)

@login_required
def detail_versement_direction(request, versement_id):
    """Détail d'un versement (vue direction)"""

    versement = get_object_or_404(
        VersementBancaire.objects.select_related(
            'superviseur', 'superviseur__user',
            'effectue_par', 'effectue_par__user'
        ),
        id=versement_id
    )
    responsable = versement.effectue_par or versement.superviseur
    depenses = versement.depenses.all()
    recus = versement.recus.all()

    total_depenses = versement.total_depenses_associees
    montant_net = versement.montant_total - total_depenses

    context = {
        'versement': versement,
        'responsable': responsable,
        'depenses': depenses,
        'recus': recus,
        'total_depenses': total_depenses,
        'montant_net': montant_net,

        # 🔑 ROT = acteur principal
        'rot': versement.effectue_par,
    }

    return render(
        request,
        'direction/factures/detail_versement.html',
        context
    )

from django.utils.dateparse import parse_date

from django.utils.dateparse import parse_date

from django.db.models import Sum
from django.utils.dateparse import parse_date
from decimal import Decimal

@login_required
def liste_depenses(request):
    # 🔹 QuerySet de base (toutes les dépenses)
    base_qs = Depense.objects.select_related(
        'effectue_par', 'effectue_par__user', 'versement'
    )

    # 🔹 Total GLOBAL (sans aucun filtre)
    total_global = (
        base_qs.aggregate(total=Sum('montant'))['total']
        or Decimal('0.00')
    )

    # 🔹 On clone pour appliquer les filtres
    depenses = base_qs.order_by('-date_depense')

    # 🔹 Filtre catégorie
    categorie = request.GET.get('categorie')
    if categorie:
        depenses = depenses.filter(categorie=categorie)

    # 🔹 Filtre période (direction)
    date_debut_raw = request.GET.get('date_debut')
    date_fin_raw = request.GET.get('date_fin')

    date_debut = parse_date(date_debut_raw) if date_debut_raw else None
    date_fin = parse_date(date_fin_raw) if date_fin_raw else None

    if date_debut:
        depenses = depenses.filter(date_depense__gte=date_debut)

    if date_fin:
        depenses = depenses.filter(date_depense__lte=date_fin)

    # 🔹 Total FILTRÉ
    total_filtre = (
        depenses.aggregate(total=Sum('montant'))['total']
        or Decimal('0.00')
    )

    context = {
        'depenses': depenses,
        'categories': Depense._meta.get_field('categorie').choices,
        'categorie_active': categorie,
        'date_debut': date_debut_raw,
        'date_fin': date_fin_raw,
        'total_global': total_global,
        'total_filtre': total_filtre,
    }

    return render(
        request,
        'direction/factures/liste_depenses.html',
        context
    )



@login_required
def detail_depense(request, depense_id):
    depense = get_object_or_404(
        Depense.objects.select_related(
            'effectue_par', 'effectue_par__user', 'versement'
        ),
        id=depense_id
    )

    return render(
        request,
        'direction/factures/detail_depense.html',
        {'depense': depense}
    )


@login_required
def analyse_financiere_direction(request):

    annee = int(request.GET.get("annee", 2026))
    mois = request.GET.get("mois")
    mois = int(mois) if mois else None

    data = AnalyseFinanciereDirectionService.build(
        annee=annee,
        mois=mois
    )

    return render(
        request,
        "direction/factures/analyse_financiere.html",
        {"data": data}
    )

##################
# Fournisseur    #
###################

class AnalyseFournisseursView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vue pour l'analyse des fournisseurs"""
    
    def test_func(self):
        return self.request.user.agent.est_direction 
    
    def get(self, request):
        analyse_data = FournisseurAnalyseService.get_analyse_globale()
    
        context = {
            'analyse_data': analyse_data['analyse_data'],
            'kpi_globaux': analyse_data['kpi_globaux'],
        }
    
        return render(
            request,
            'direction/analyses/fournisseurs/liste.html',
            context
        )
    
class DetailFournisseurView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vue détaillée d'un fournisseur"""
    
    def test_func(self):
        return self.request.user.agent.est_direction 
    
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
        
        # Ajouter les informations sur les factures
        fournisseur = Fournisseur.objects.get(pk=pk)
        
        # Nombre de factures pour ce fournisseur
        nombre_factures = FactureLotEntrepot.objects.filter(
            lot__fournisseur=fournisseur
        ).count()
        
        # Montant total facturé
        montant_total_factures = FactureLotEntrepot.objects.filter(
            lot__fournisseur=fournisseur
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
        
        # Dernières factures (5 max)
        dernieres_factures = FactureLotEntrepot.objects.filter(
            lot__fournisseur=fournisseur
        ).select_related('lot', 'lot__produit').order_by('-date_upload')[:5]
        
        context = {
            **detail_data,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nombre_factures': nombre_factures,
            'montant_total_factures': montant_total_factures,
            'dernieres_factures': dernieres_factures,
        }
        
        return render(
            request,
            'direction/analyses/fournisseurs/detail.html',
            context
        )

@login_required
def liste_paiements_fournisseur(request, fournisseur_id):
    """
    Liste des paiements d'un fournisseur
    """
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    
    # Récupérer les paiements (actifs et supprimés séparément)
    paiements_actifs = PaiementFournisseur.objects.filter(
        fournisseur=fournisseur,
        est_supprime=False
    ).select_related('lot', 'superviseur', 'cree_par').order_by('-date_paiement', '-created_at')
    
    paiements_supprimes = PaiementFournisseur.objects.filter(
        fournisseur=fournisseur,
        est_supprime=True
    ).select_related('lot', 'superviseur', 'cree_par', 'supprime_par').order_by('-date_suppression')
    
    # Calculer les totaux
    total_paye = paiements_actifs.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
    total_supprime = paiements_supprimes.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
    
    # Récupérer les stats du fournisseur
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    stats = FournisseurAnalyseService.get_detail_fournisseur(
        fournisseur.id, 
        date_debut, 
        date_fin
    )
    
    return render(request, 'direction/analyses/fournisseurs/paiements/liste_paiements.html', {
        'fournisseur': fournisseur,
        'paiements_actifs': paiements_actifs,
        'paiements_supprimes': paiements_supprimes,
        'total_paye': total_paye,
        'total_supprime': total_supprime,
        'stats': stats,
        'date_debut': date_debut,
        'date_fin': date_fin,
    })

@login_required
def creer_paiement_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    reste_a_payer = FournisseurAnalyseService.get_reste_a_payer_fournisseur(fournisseur.id)

    if request.method == 'POST':
        form = PaiementFournisseurForm(
            request.POST,
            fournisseur=fournisseur
        )
        if form.is_valid():
            paiement = form.save(commit=False)
            paiement.fournisseur = fournisseur
            paiement.cree_par = request.user
            paiement.save()

            messages.success(
                request,
                f"Paiement de {paiement.montant} FCFA enregistré."
            )
            return redirect('liste_paiements_fournisseur', fournisseur_id=fournisseur.id)
    else:
        initial = {'date_paiement': timezone.now().date()}
        if request.GET.get('lot'):
            lot_id = request.GET.get('lot')
            if lot_id:
                initial['lot'] = LotEntrepot.objects.filter(
                    id=lot_id,
                    fournisseur=fournisseur
                ).first()

        if request.GET.get('montant'):
            initial['montant'] = request.GET.get('montant')

        form = PaiementFournisseurForm(
            initial=initial,
            fournisseur=fournisseur
        )

    return render(request, 'direction/analyses/fournisseurs/paiements/form_paiement.html', {
        'form': form,
        'fournisseur': fournisseur,
        'reste_a_payer': reste_a_payer,
        'action': 'créer',
    })

@login_required
def modifier_paiement_fournisseur(request, paiement_id):
    paiement = get_object_or_404(
        PaiementFournisseur,
        id=paiement_id,
        est_supprime=False
    )
    fournisseur = paiement.fournisseur
    lot = paiement.lot

    # 🧠 Calcul du plafond CONTEXTUEL
    if lot:
        total_paye_lot = PaiementFournisseur.objects.filter(
            lot=lot,
            est_supprime=False
        ).exclude(id=paiement.id).aggregate(
            total=Sum('montant')
        )['total'] or Decimal('0.00')

        reste_a_payer = max(
            lot.dette_lot - total_paye_lot,
            Decimal('0.00')
        )
    else:
        # Cas très rare : paiement sans lot
        reste_a_payer = FournisseurAnalyseService.get_reste_a_payer_fournisseur(
            fournisseur.id
        ) + paiement.montant

    if request.method == 'POST':
        form = PaiementFournisseurForm(
            request.POST,
            instance=paiement,
            fournisseur=fournisseur
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Paiement modifié avec succès.")
            return redirect(
                'liste_paiements_fournisseur',
                fournisseur_id=fournisseur.id
            )
    else:
        form = PaiementFournisseurForm(
            instance=paiement,
            fournisseur=fournisseur
        )

    return render(
        request,
        'direction/analyses/fournisseurs/paiements/form_paiement.html',
        {
            'form': form,
            'fournisseur': fournisseur,
            'paiement': paiement,
            'reste_a_payer': reste_a_payer,  # ✅ CONTEXTUEL
            'action': 'modifier',
        }
    )


@login_required
def supprimer_paiement_fournisseur(request, paiement_id):
    """
    Soft delete d'un paiement
    """
    paiement = get_object_or_404(PaiementFournisseur, id=paiement_id, est_supprime=False)
    fournisseur = paiement.fournisseur
    
    if request.method == 'POST':
        raison = request.POST.get('raison_suppression', '')
        paiement.soft_delete(user=request.user, raison=raison)
        
        messages.success(request, f"Paiement de {paiement.montant} FCFA supprimé.")
        return redirect('liste_paiements_fournisseur', fournisseur_id=fournisseur.id)
    
    return render(request, 'direction/analyses/fournisseurs/paiements/confirmer_suppression.html', {
        'paiement': paiement,
        'fournisseur': fournisseur,
    })

@login_required
def restaurer_paiement_fournisseur(request, paiement_id):
    """
    Restaurer un paiement supprimé
    """
    paiement = get_object_or_404(PaiementFournisseur, id=paiement_id, est_supprime=True)
    fournisseur = paiement.fournisseur
    
    paiement.restaurer()
    messages.success(request, f"Paiement de {paiement.montant} FCFA restauré.")
    
    return redirect('liste_paiements_fournisseur', fournisseur_id=fournisseur.id)



@login_required
def detail_paiement_fournisseur(request, paiement_id):
    paiement = get_object_or_404(PaiementFournisseur, id=paiement_id)

    fournisseur = paiement.fournisseur
    lot = paiement.lot

    valeur_stock_initiale = Decimal('0.00')
    reste_a_payer = None

    if lot:
        # Fallback si valeur_stock_initiale est NULL
        valeur_stock_initiale = (
            lot.valeur_stock_initiale
            if lot.valeur_stock_initiale is not None
            else lot.quantite_initiale * lot.prix_achat_unitaire
        )

        reste_a_payer = valeur_stock_initiale - lot.total_paye_lot

    return render(
        request,
        'direction/analyses/fournisseurs/paiements/detail_paiement.html',
        {
            'paiement': paiement,
            'fournisseur': fournisseur,
            'lot': lot,
            'valeur_stock_initiale': valeur_stock_initiale,
            'reste_a_payer': reste_a_payer,
        }
    )


###################
# Cloture         #
###################


from django.core.exceptions import PermissionDenied
from django.db import transaction

@login_required
def cloturer_periode(request, cloture_id):
    if not request.user.agent.est_direction:
        raise PermissionDenied

    with transaction.atomic():
        cloture = get_object_or_404(ClotureMensuelle, id=cloture_id)

        if cloture.est_cloture:
            return redirect('liste_clotures')

        cloture.date_fin_periode = timezone.now().date() - timedelta(days=1)
        
        data = calculer_solde_periode(
            superviseur=cloture.superviseur,
            date_debut=cloture.date_debut_periode,
            date_fin=cloture.date_fin_periode,
            solde_ouverture=cloture.solde_ouverture
        )

        cloture.solde_cloture = data['solde_cloture']
        cloture.est_cloture = True
        cloture.date_cloture = timezone.now()
        cloture.cloture_par = request.user
        cloture.save()

        cloture.superviseur.remettre_solde_operationnel_a_zero(
            cloture=cloture,
            par=request.user
        )

    return redirect('liste_clotures')


def ouvrir_nouvelle_periode(superviseur, date_debut, annee, mois):
    derniere = ClotureMensuelle.objects.filter(
        superviseur=superviseur,
        est_cloture=True
    ).order_by('-date_fin_periode').first()

    solde_ouverture = (
        derniere.solde_cloture if derniere else Decimal('0.00')
    )

    return ClotureMensuelle.objects.create(
        superviseur=superviseur,
        annee=annee,
        mois=mois,
        date_debut_periode=date_debut,
        date_fin_periode=date_debut,  # sera ajusté à la clôture
        solde_ouverture=solde_ouverture,
        solde_cloture=solde_ouverture
    )

@login_required
def liste_clotures(request):
    clotures = ClotureMensuelle.objects.select_related(
        'superviseur'
    ).order_by('-date_debut_periode')

    return render(
        request,
        'direction/analyses/clotures/liste.html',
        {'clotures': clotures}
    )

@login_required
def apercu_cloture(request, cloture_id):
    cloture = get_object_or_404(ClotureMensuelle, id=cloture_id)

    data = calculer_solde_periode(
        superviseur=cloture.superviseur,
        date_debut=cloture.date_debut_periode,
        date_fin=cloture.date_fin_periode,
        solde_ouverture=cloture.solde_ouverture
    )

    solde_estime = data['solde_cloture']
    if cloture.est_cloture:
        ecart = solde_estime - cloture.solde_cloture
    else:
        ecart = None
    
    return render(
        request,
        'direction/analyses/clotures/apercu.html',
        {
            'cloture': cloture,
            'data': data,
            'solde_estime': solde_estime,
            'ecart': ecart
        }
    )



@login_required
def admin_create_agent(request):
    if request.method == 'POST':
        form = DirectionAgentCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Agent créé avec succès")
            return redirect('agent_dashboard')
    else:
        form = DirectionAgentCreationForm()

    return render(request, 'direction/agents/agent_create.html', {'form': form})



from django.contrib.auth.decorators import login_required, user_passes_test


from direction.forms import CalculSalaireForm
from direction.services.salaire_service import SalaireService


@login_required
@user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'agent') and u.agent.est_direction)
def calcul_salaires(request):
    """Vue principale pour le calcul des salaires"""
    form = CalculSalaireForm(request.GET or None)
    resultats = None
    
    # Définir les dates par défaut (mois précédent)
    aujourdhui = timezone.now().date()
    premier_du_mois = date(aujourdhui.year, aujourdhui.month, 1)
    dernier_du_mois_precedent = premier_du_mois - timedelta(days=1)
    premier_du_mois_precedent = date(
        dernier_du_mois_precedent.year, 
        dernier_du_mois_precedent.month, 
        1
    )
    
    if request.method == 'GET' and any(key in request.GET for key in ['date_debut', 'date_fin']):
        if form.is_valid():
            date_debut = form.cleaned_data['date_debut']
            date_fin = form.cleaned_data['date_fin']
            agent = form.cleaned_data['agent']
            
            if agent:
                # Calcul pour un agent spécifique
                resultat_agent = SalaireService.calculer_salaire_agent(
                    agent.id, date_debut, date_fin
                )
                if resultat_agent:
                    resultats = {
                        "resultats": [resultat_agent],
                        "totaux": {
                            "total_salaire_base": resultat_agent["salaire_base"],
                            "total_incentive": resultat_agent["incentive"],
                            "total_general": resultat_agent["salaire_total"],
                            "nombre_agents": 1
                        },
                        "periode": {
                            "debut": date_debut,
                            "fin": date_fin
                        }
                    }
                    messages.success(request, f"Salaire calculé pour {agent.full_name}")
                else:
                    messages.error(request, "Impossible de calculer le salaire pour cet agent")
            else:
                # Calcul pour tous les agents
                resultats = SalaireService.calculer_salaires_tous_agents(date_debut, date_fin)
                messages.success(
                    request, 
                    f"Salaires calculés pour {resultats['totaux']['nombre_agents']} agents"
                )
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire")
    
    context = {
        'form': form,
        'resultats': resultats,
        'premier_du_mois_precedent': premier_du_mois_precedent,
        'dernier_du_mois_precedent': dernier_du_mois_precedent,
        'page_title': 'Calcul des Salaires'
    }
    
    return render(request, 'direction/salaires/calcul_salaires.html', context)


@login_required
@user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'agent') and u.agent.est_direction)
def detail_salaire_agent(request, agent_id):
    """Détail du salaire d'un agent"""
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        messages.error(request, "Agent non trouvé")
        return redirect('direction:calcul_salaires')
    
    # Par défaut : mois précédent
    aujourdhui = timezone.now().date()
    premier_du_mois = date(aujourdhui.year, aujourdhui.month, 1)
    dernier_du_mois_precedent = premier_du_mois - timedelta(days=1)
    premier_du_mois_precedent = date(
        dernier_du_mois_precedent.year, 
        dernier_du_mois_precedent.month, 
        1
    )
    
    date_debut = premier_du_mois_precedent
    date_fin = dernier_du_mois_precedent
    
    if request.method == 'POST':
        date_debut = request.POST.get('date_debut', premier_du_mois_precedent)
        date_fin = request.POST.get('date_fin', dernier_du_mois_precedent)
        
        if isinstance(date_debut, str):
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
        if isinstance(date_fin, str):
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
    
    # Calculer le salaire
    resultat = SalaireService.calculer_salaire_agent(agent_id, date_debut, date_fin)
    
    if not resultat:
        messages.error(request, "Impossible de calculer le salaire pour cet agent")
        return redirect('direction:calcul_salaires')
    
    # Récupérer les ventes détaillées pour l'incentive
    ventes_incentive = []
    recouvrements = Recouvrement.objects.filter(
        agent_id=agent_id,
        bonus_accorde=True,
        date_recouvrement__date__gte=date_debut,
        date_recouvrement__date__lte=date_fin,
        vente__type_vente="detail"
    ).select_related(
        "vente__detail_distribution__lot__produit",
        "vente__client"
    )
    
    for r in recouvrements:
        produit = r.vente.detail_distribution.lot.produit
        ratio = SalaireService.CONVERSION_CARTON.get(produit.nom)
        if ratio:
            cartons = Decimal(r.vente.quantite) / ratio
            incentive = cartons * Decimal("100")
            ventes_incentive.append({
                'date': r.date_recouvrement,
                'produit': produit.nom,
                'quantite': r.vente.quantite,
                'ratio_carton': ratio,
                'cartons': cartons,
                'incentive': incentive,
                'client': r.vente.client.nom if r.vente.client else "Non spécifié"
            })
    
    context = {
        'agent': agent,
        'resultat': resultat,
        'ventes_incentive': ventes_incentive,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'page_title': f'Détail Salaire - {agent.full_name}'
    }
    
    return render(request, 'direction/salaires/detail_salaire.html', context)


@login_required
@user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'agent') and u.agent.est_direction)
def export_salaires_excel(request):
    """Export des salaires en Excel"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        date_debut = datetime.strptime(data.get('date_debut'), '%Y-%m-%d').date()
        date_fin = datetime.strptime(data.get('date_fin'), '%Y-%m-%d').date()
        
        # Générer le fichier Excel
        excel_file = SalaireService.generer_rapport_excel(date_debut, date_fin)
        
        # Créer la réponse HTTP
        response = HttpResponse(
            excel_file.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="salaires_{date_debut}_{date_fin}.xlsx"'
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'agent') and u.agent.est_direction)
def api_calcul_salaire_rapide(request):
    """API pour calcul rapide de salaire (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        agent_id = data.get('agent_id')
        date_debut = datetime.strptime(data.get('date_debut'), '%Y-%m-%d').date()
        date_fin = datetime.strptime(data.get('date_fin'), '%Y-%m-%d').date()
        
        resultat = SalaireService.calculer_salaire_agent(agent_id, date_debut, date_fin)
        
        if resultat:
            return JsonResponse({
                'success': True,
                'data': {
                    'agent': resultat['agent'].full_name,
                    'quantite_totale': str(resultat['quantite_totale']),
                    'salaire_base': str(resultat['salaire_base']),
                    'incentive': str(resultat['incentive']),
                    'salaire_total': str(resultat['salaire_total']),
                    'date_debut': date_debut.strftime('%d/%m/%Y'),
                    'date_fin': date_fin.strftime('%d/%m/%Y')
                }
            })
        else:
            return JsonResponse({'success': False, 'error': 'Agent non trouvé'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})




from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import (
    F,
    Q,
    Sum,
    Value,
    DecimalField,
    ExpressionWrapper
)
from django.db.models.functions import Coalesce
from django.shortcuts import render

from core.models import (
    Agent,
    Produit,
    DetailDistribution,
)


def suivi_distributions(request):

    details = (
        DetailDistribution.objects
        .select_related(
            "lot",
            "lot__produit",
            "distribution",
            "distribution__superviseur",
            "distribution__agent_terrain",
        )
        .annotate(

            # Total vendu RÉEL
            total_vendu=Coalesce(
                Sum(
                    "vente__quantite",
                    filter=Q(vente__est_supprime=False)
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=10,
                    decimal_places=2
                )
            )
        )
        .annotate(

            # Stock restant
            restant=ExpressionWrapper(
                F("quantite") - F("total_vendu"),
                output_field=DecimalField(
                    max_digits=10,
                    decimal_places=2
                )
            )
        )
    )

    # ==================================================
    # FILTRES
    # ==================================================

    superviseur_id = request.GET.get("superviseur")
    agent_id = request.GET.get("agent")
    produit_id = request.GET.get("produit")
    statut = request.GET.get("statut")

    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    if superviseur_id:
        details = details.filter(
            distribution__superviseur_id=superviseur_id
        )

    if agent_id:
        details = details.filter(
            distribution__agent_terrain_id=agent_id
        )

    if produit_id:
        details = details.filter(
            lot__produit_id=produit_id
        )

    if date_debut:
        details = details.filter(
            distribution__date_distribution__date__gte=date_debut
        )

    if date_fin:
        details = details.filter(
            distribution__date_distribution__date__lte=date_fin
        )

    # ==================================================
    # STATUTS
    # ==================================================

    if statut == "restant":
        details = details.filter(restant__gt=0)

    elif statut == "ecoule":
        details = details.filter(restant__lte=0)

    elif statut == "dormant":
        details = details.filter(restant__gt=0)

    # ==================================================
    # PAGINATION
    # ==================================================

    paginator = Paginator(
        details.order_by(
            "-distribution__date_distribution"
        ),
        20
    )

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,

        "superviseurs": Agent.objects.filter(
            type_agent='entrepot'
        ),

        "agents": Agent.objects.filter(
            type_agent__in=['terrain', 'agent_gros','stagiaire','agent_polivalent']
        ),

        "produits": Produit.objects.all(),
        "labels_agents": {
            'terrain': 'Mami',
            'agent_gros': 'Agent Gros',
            'stagiaire': 'Stagiaire',
            'agent_polivalent': 'Polyvalent'
        }
    }

    return render(
        request,
        "direction/analyses/stock/suivi_distributions.html",
        context
    )

# direction/views.py

from django.shortcuts import render
from core.models import Agent, Alerte
from direction.services.alertes.solde import SoldeAlertService


def monitoring_alertes_dashboard(request):

    # superviseurs actifs
    superviseurs = Agent.objects.filter(
        type_agent="entrepot",
        est_actif=True
    ).select_related("user")

    data_superviseurs = []

    for sup in superviseurs:

        # recalcul solde + génération alertes
        solde = SoldeAlertService.check_superviseur_solde(sup)

        # alertes non vues
        alertes = Alerte.objects.filter(
            superviseur=sup.user,
            est_vue=False
        ).order_by("-date_creation")[:10]

        data_superviseurs.append({
            "superviseur": sup,
            "solde": solde,
            "alertes": alertes,
        })

    # alertes globales récentes
    alertes_globales = Alerte.objects.all().order_by("-date_creation")[:30]

    return render(request, "direction/monitoring/dashboard.html", {
        "data_superviseurs": data_superviseurs,
        "alertes_globales": alertes_globales,
    })