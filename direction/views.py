from direction.services.product_analysis_service import ProductAnalysisService
from django.contrib.auth.decorators import login_required
from core.models import (
    Agent, Client, Vente, Produit, 
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,PaiementFournisseur,
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
from datetime import date, datetime, timedelta
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

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.shortcuts import render
from datetime import datetime, timedelta
from decimal import Decimal
from core.models import VersementBancaire, Agent, Depense
from django.db.models import Sum, Count, Avg, Q, F


# views_direction.py - Vues direction (lecture seule)
from django.contrib import messages
from django.shortcuts import redirect

from datetime import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum, Q
from django.utils import timezone

from core.forms import RapportDettesForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from core.forms import PaiementFournisseurForm

# direction/views.py

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db.models import Sum, Q
from decimal import Decimal
from datetime import datetime

from core.models import Fournisseur, PaiementFournisseur, LotEntrepot, Agent

from direction.services.fournisseur_service import FournisseurAnalyseService

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
    # Vérifier permissions
    
    lots_avec_facture = LotEntrepot.objects.exclude(facture='').select_related(
        'fournisseur', 'produit'
    ).order_by('-date_reception')
    
    # Filtrer par fournisseur (optionnel)
    fournisseur_id = request.GET.get('fournisseur')
    if fournisseur_id:
        lots_avec_facture = lots_avec_facture.filter(fournisseur_id=fournisseur_id)
    
    # Filtrer par date (optionnel)
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    if date_debut and date_fin:
        lots_avec_facture = lots_avec_facture.filter(
            date_reception__date__gte=date_debut,
            date_reception__date__lte=date_fin
        )
    
    # Calculer les totaux
    total_montant = sum(l.valeur_stock_initiale for l in lots_avec_facture if l.valeur_stock_initiale)
    
    context = {
        'lots_avec_facture': lots_avec_facture,
        'total_montant': total_montant,
        'title': 'Factures Fournisseurs - Direction'
    }
    return render(request, 'direction/factures/liste_factures_fournisseurs.html', context)



@login_required
def liste_versements_direction(request):
    """Liste complète des versements (vue direction) avec filtres avancés"""
    # Base queryset
    versements = VersementBancaire.objects.all().select_related(
        'superviseur', 'superviseur__user'
    ).prefetch_related(
        'depenses', 'recus'
    ).order_by('-date_versement_reelle')
    
    # ============ FILTRES DISPONIBLES ============
    filtres_actifs = {}
    
    # 1. Filtre par superviseur
    superviseur_id = request.GET.get('superviseur')
    if superviseur_id and superviseur_id != '':
        versements = versements.filter(superviseur_id=superviseur_id)
        filtres_actifs['superviseur'] = superviseur_id
    
    # 2. Filtre périodique simplifié (mois, année, custom)
    periode = request.GET.get('periode')
    
    if periode:
        aujourdhui = timezone.now().date()
        
        if periode == 'mois_courant':
            # Mois en cours
            debut_mois = aujourdhui.replace(day=1)
            fin_mois = (debut_mois + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            versements = versements.filter(
                date_versement_reelle__date__gte=debut_mois,
                date_versement_reelle__date__lte=fin_mois
            )
            filtres_actifs['periode'] = "Mois en cours"
            
        elif periode == 'annee_courante':
            # Année en cours
            debut_annee = aujourdhui.replace(month=1, day=1)
            fin_annee = aujourdhui.replace(month=12, day=31)
            versements = versements.filter(
                date_versement_reelle__date__gte=debut_annee,
                date_versement_reelle__date__lte=fin_annee
            )
            filtres_actifs['periode'] = "Année en cours"
    
    # 3. Filtre par dates personnalisées (si custom sélectionné)
    if periode == 'custom':
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        
        if date_debut and date_fin:
            versements = versements.filter(
                date_versement_reelle__date__gte=date_debut,
                date_versement_reelle__date__lte=date_fin
            )
            filtres_actifs['periode'] = "Période personnalisée"
            filtres_actifs['date_debut'] = date_debut
            filtres_actifs['date_fin'] = date_fin
    
    # 4. Filtre par type de versement
    type_versement = request.GET.get('type_versement')
    if type_versement and type_versement != 'tous':
        if type_versement == 'vente':
            versements = versements.filter(montant_vente__gt=0, montant_hors_vente=0)
        elif type_versement == 'hors_vente':
            versements = versements.filter(montant_hors_vente__gt=0, montant_vente=0)
        elif type_versement == 'mixte':
            versements = versements.filter(montant_vente__gt=0, montant_hors_vente__gt=0)
        filtres_actifs['type_versement'] = type_versement
    
    # 5. Filtre par montant minimum
    montant_min = request.GET.get('montant_min')
    if montant_min:
        try:
            montant_min_decimal = Decimal(montant_min)
            versements = versements.filter(
                Q(montant_vente__gte=montant_min_decimal) | 
                Q(montant_hors_vente__gte=montant_min_decimal)
            )
            filtres_actifs['montant_min'] = montant_min
        except (ValueError, Exception):
            pass
    
    # 6. Filtre avec/sans reçus
    avec_recus = request.GET.get('avec_recus')
    if avec_recus:
        if avec_recus == 'oui':
            versements = versements.annotate(num_recus=Count('recus')).filter(num_recus__gt=0)
        elif avec_recus == 'non':
            versements = versements.annotate(num_recus=Count('recus')).filter(num_recus=0)
        filtres_actifs['avec_recus'] = avec_recus
    
    # ============ CALCUL DES STATISTIQUES ============
    # Totaux pour les versements filtrés
    stats = versements.aggregate(
        total_vente=Sum('montant_vente'),
        total_hors_vente=Sum('montant_hors_vente'),
        nombre_versements=Count('id'),
        moyenne_vente=Avg('montant_vente'),
        moyenne_hors_vente=Avg('montant_hors_vente')
    )
    
    total_vente = stats['total_vente'] or Decimal('0.00')
    total_hors_vente = stats['total_hors_vente'] or Decimal('0.00')
    total_general = total_vente + total_hors_vente
    
    # Dépenses totales associées aux versements filtrés
    versement_ids = versements.values_list('id', flat=True)
    total_depenses = Depense.objects.filter(versement_id__in=versement_ids).aggregate(
        total=Sum('montant')
    )['total'] or Decimal('0.00')
    
    # ============ CONTEXT ============
    # Récupérer la liste des superviseurs avec leur nom complet
    superviseurs_list = Agent.objects.filter(type_agent='entrepot').select_related('user')
    
    context = {
        'versements': versements,
        'total_vente': total_vente,
        'total_hors_vente': total_hors_vente,
        'total_general': total_general,
        'total_depenses': total_depenses,
        'net_verse': total_general - total_depenses,
        
        # Filtres
        'filtres_actifs': filtres_actifs,
        'superviseurs': superviseurs_list,
        'nombre_versements_filtres': stats['nombre_versements'] or 0,
        'moyenne_hors_vente': stats['moyenne_hors_vente'] or Decimal('0.00'),
        
        # Options de filtres simplifiées
        'periodes_disponibles': [
            ('', 'Sélectionner période'),
            ('mois_courant', 'Mois en cours'),
            ('annee_courante', 'Année en cours'),
            ('custom', 'Période personnalisée'),
        ],
        
        'types_versement': [
            ('tous', 'Tous les types'),
            ('vente', 'Vente uniquement'),
            ('hors_vente', 'Hors vente uniquement'),
            ('mixte', 'Mixte'),
        ],
        
        'options_recus': [
            ('', 'Peu importe'),
            ('oui', 'Avec reçus'),
            ('non', 'Sans reçu'),
        ],
    }
    
    return render(request, 'direction/factures/liste_versements.html', context)

@login_required
def detail_versement_direction(request, versement_id):
    """Détail d'un versement (vue direction)"""
    # Vérifier permissions
    
    versement = get_object_or_404(VersementBancaire.objects.select_related('superviseur'), id=versement_id)
    
    # Récupérer les dépenses associées
    depenses = versement.depenses.all()
    
    # Récupérer les reçus associés
    recus = versement.recus.all()
    
    # Calculer les statistiques
    total_depenses = versement.total_depenses_associees
    montant_net = versement.montant_total - total_depenses
    
    context = {
        'versement': versement,
        'depenses': depenses,
        'recus': recus,
        'total_depenses': total_depenses,
        'montant_net': montant_net,
    }
    
    return render(request, 'direction/factures/detail_versement.html', context)

# views.py




@login_required
def analyse_financiere_direction(request):
    """
    VUE DIRECTION – ANALYSE FINANCIÈRE
    - Filtre annuel OU mensuel
    - KPI réels
    - Fournisseurs visibles
    """

    today = timezone.now().date()

    # =========================
    # FILTRES
    # =========================
    annee = int(request.GET.get('annee', today.year))
    mois = request.GET.get('mois')  # volontairement str ou None

    if mois:
        mois = int(mois)
        debut_periode = date(annee, mois, 1)
        if mois == 12:
            fin_periode = date(annee + 1, 1, 1) - timedelta(days=1)
        else:
            fin_periode = date(annee, mois + 1, 1) - timedelta(days=1)
        mode_filtre = "mensuel"
    else:
        debut_periode = date(annee, 1, 1)
        fin_periode = date(annee, 12, 31)
        mode_filtre = "annuel"

    # =========================
    # 1️⃣ CHIFFRE D’AFFAIRES
    # =========================
    ventes = Vente.objects.filter(
        date_vente__date__range=(debut_periode, fin_periode),
        est_supprime=False
    )

    ca_total = ventes.aggregate(
        total=Sum(F('quantite') * F('prix_vente_unitaire'))
    )['total'] or Decimal('0.00')

    ca_gros = ventes.filter(type_vente='gros').aggregate(
        total=Sum(F('quantite') * F('prix_vente_unitaire'))
    )['total'] or Decimal('0.00')

    ca_detail = ventes.filter(type_vente='detail').aggregate(
        total=Sum(F('quantite') * F('prix_vente_unitaire'))
    )['total'] or Decimal('0.00')

    # =========================
    # 2️⃣ VERSEMENTS BANCAIRES
    # =========================
    versements = VersementBancaire.objects.filter(
        date_versement_reelle__date__range=(debut_periode, fin_periode)
    )

    total_verse = sum(v.montant_total for v in versements)

    # =========================
    # 3️⃣ DÉPENSES
    # =========================
    total_depenses = Depense.objects.filter(
        versement__in=versements
    ).aggregate(
        total=Sum('montant')
    )['total'] or Decimal('0.00')

    # =========================
    # 4️⃣ FOURNISSEURS (IMPORTANT)
    # =========================
    fournisseurs = Fournisseur.objects.all()

    dette_consomme_fournisseurs = Decimal('0.00')
    for f in fournisseurs:
        dette_consomme_fournisseurs += f.dette_consomme

    # =========================
    # 5️⃣ ANALYSE PAR SUPERVISEUR
    # =========================
    analyse_superviseurs = []

    superviseurs = Agent.objects.filter(type_agent='entrepot')
    for sup in superviseurs:
        analyse_superviseurs.append({
            'superviseur': sup,
            'total_verse': sup.total_versements_bancaires,
            'total_depenses': sup.total_depenses_superviseur,
            'solde_actuel': sup.solde_superviseur,
            'argent_en_possession': sup.argent_en_possession,
        })

    # =========================
    # CONTEXTE
    # =========================
    context = {
        # Filtres
        'annee_selectionnee': annee,
        'mois_selectionne': mois,
        'mode_filtre': mode_filtre,
        'debut_periode': debut_periode,
        'fin_periode': fin_periode,

        # KPI
        'ca_total': ca_total,
        'ca_gros': ca_gros,
        'ca_detail': ca_detail,
        'total_verse': total_verse,
        'total_depenses': total_depenses,
        'dette_consomme_fournisseurs': dette_consomme_fournisseurs,

        # Détails
        'analyse_superviseurs': analyse_superviseurs,
        'fournisseurs': fournisseurs,

        # UI
        'mois_choices': [
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
            (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
            (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
        ],
        'annee_choices': range(2023, today.year + 2),
    }

    return render(
        request,
        'direction/factures/analyse_financiere.html',
        context
    )

##################
# Fournisseur    #
###################

class AnalyseFournisseursView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vue pour l'analyse des fournisseurs"""
    
    def test_func(self):
        return self.request.user.agent.est_direction 
    
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
