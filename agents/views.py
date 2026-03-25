# Django imports
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.paginator import Paginator

# DB / ORM
from django.db import models, transaction
from django.db.models import (
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField,Prefetch
)
from django.db.models.functions import Coalesce

from django import forms
from django.core.exceptions import ValidationError 
from django.utils import timezone
from datetime import date, timedelta
# Python stdlib
from datetime import timedelta
from decimal import Decimal
import json

from urllib3 import request

# Project models
from agents.services.analyse_operationnelle_service import AnalyseOperationnelleService
from agents.services.analyse_operationnelle_service import AnalyseOperationnelleService
from core.models import (
    Agent, Client, Vente, Produit,Depense,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,
    Recouvrement,VersementBancaire,VersementBancaire,RecuVersement,
    AffectationLotSuperviseur,RecouvrementSuperviseur
)

# Project forms
from core.forms import (
    FactureLotForm,  DistributionForm, ReceptionLotForm, 
    DetteForm, PaiementDetteForm,RecouvrementForm,
    FournisseurForm,VersementForm

)

from agents.forms import (
                           
                            SupervisorTerrainAgentCreationForm,
                            
                            DirectionAgentCreationForm,
                            RotSupervisorCreationForm,
                            RotAffectationLotSuperviseurForm,
                            SupervisorDistributionForm,
                            RecouvrementSuperviseurForm,
                            SupervisorTerrainAgentUpdateForm,
                            VenteSuperviseurSimplifieeForm
                            
                            )

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


from django.contrib.auth import authenticate, login
from django.contrib import messages
from core.forms import TelephoneOrUsernameLoginForm
from core.models import Agent
from django.core.paginator import Paginator

from agents.services.superviseur_service import SuperviseurDashboardService


from agents.services.agent_dashboard_service import AgentDashboardService
from agents.services.superviseur_stock_service import SuperviseurStockService
from agents.services.rot_dashboard_service import RotDashboardService
from django.db.models import DecimalField, ExpressionWrapper
from django.utils.dateparse import parse_date

def safe_parse_date(value):
    if isinstance(value, str) and value:
        return parse_date(value)
    return None

@login_required
def tableau_de_bord_superviseur(request):
    """
    Vue dashboard superviseur - Périmètre restreint
    Ne montre que le stock attribué et les agents sous sa responsabilité
    """
    context = SuperviseurDashboardService.build_dashboard_perimetre(request.user)

    if not context:
        messages.error(request, "Accès réservé aux superviseurs")
        return redirect('login')

    return render(
        request,
        'agents/dashboards/superviseur.html',
        context
    )

@login_required
def tableau_de_bord_rot(request):
    """
    Tableau de bord du ROT (Responsable Opérations et Trésorerie)
    Vision pilotage : stock, superviseurs, argent
    """
    agent = request.user.agent  
    context = RotDashboardService.build_dashboard(agent)

    return render(
        request,
        'agents/dashboards/rot.html',
        context
    )




@login_required
def dashboard_agent(request):
    service = AgentDashboardService(request.user)
    context = service.get_dashboard_context()

    if context is None:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')

    return render(
        request,
        'agents/dashboards/agent.html',
        context
    )


#
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from urllib.parse import urlencode
from django.utils.dateparse import parse_date

@login_required
def superviseur_lots_affectes(request):
    agent = request.user.agent

    if not agent.est_superviseur:
        return redirect('access_denied')

    # =========================
    # FILTRES TEMPORELS
    # =========================
    periode = request.GET.get('periode')  # today, 7j, 30j


    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    # 🔥 CLEAN
    date_debut = parse_date(date_debut) if date_debut else None
    date_fin = parse_date(date_fin) if date_fin else None
    lots_qs = AffectationLotSuperviseur.objects.filter(
        superviseur=agent
    )

    # 🔹 filtres rapides
    today = timezone.now()

    if periode == 'today':
        lots_qs = lots_qs.filter(date_affectation=today)

    elif periode == '7j':
        lots_qs = lots_qs.filter(
            date_affectation__gte=today - timedelta(days=7)
        )

    elif periode == '30j':
        lots_qs = lots_qs.filter(
            date_affectation__gte=today - timedelta(days=30)
        )

    # 🔹 filtre personnalisé
    if date_debut:
        lots_qs = lots_qs.filter(date_affectation__gte=date_debut)

    if date_fin:
        lots_qs = lots_qs.filter(date_affectation__lte=date_fin)

    # =========================
    # QUERY OPTIMISÉE
    # =========================
    lots_qs = (
        lots_qs
        .select_related('lot__produit', 'attribue_par__user')
        .order_by('-date_affectation')
    )

    # =========================
    # PAGINATION
    # =========================
    paginator = Paginator(lots_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # =========================
    # TRANSFORMATION
    # =========================
    lots_data = []

    for affectation in page_obj:
        taux_restant = 0
        taux_utilise = 0

        if affectation.quantite_initiale > 0:
            taux_restant = (
                affectation.quantite_restante / affectation.quantite_initiale
            ) * 100
            taux_utilise = 100 - taux_restant

        lots_data.append({
            'affectation': affectation,
            'taux_restant': round(taux_restant, 1),
            'taux_utilise': round(taux_utilise, 1),
            'statut_progress': (
                'success' if taux_restant > 50
                else 'warning' if taux_restant > 20
                else 'danger'
            ),
        })

    # =========================
    # KPI (filtrés)
    # =========================
    total_initial = sum(a.quantite_initiale for a in lots_qs)
    total_restant = sum(a.quantite_restante for a in lots_qs)

    taux_utilisation_global = 0
    if total_initial > 0:
        taux_utilisation_global = (
            (total_initial - total_restant) / total_initial
        ) * 100

    context = {
        'lots_data': lots_data,
        'page_obj': page_obj,
        'total_initial': total_initial,
        'total_restant': total_restant,
        'taux_utilisation_global': round(taux_utilisation_global, 1),
        'nombre_lots': lots_qs.count(),

        # 🔥 garder les filtres en mémoire
        'periode': periode,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    return render(
        request,
        'agents/superviseur/lots_affectes.html',
        context
    )

@login_required
def distribuer_lot_agent(request):
    superviseur = request.user.agent

    if not superviseur.est_superviseur:
        return redirect('access_denied')

    form = SupervisorDistributionForm(
        request.POST or None,
        superviseur=superviseur
    )

    # 🔹 Stock calculé à la volée
    stock_service = SuperviseurStockService(superviseur)
    stock_superviseur = stock_service.get_stock()

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "✅ Distribution effectuée avec succès")
        return redirect('liste_distribution_sup')

    return render(request, 'agents/superviseur/distribuer_lot.html', {
        'form': form,
        'stock_superviseur': stock_superviseur,
    })


@login_required
def vente_superviseur_simplifiee(request):
    superviseur = request.user.agent
    form = VenteSuperviseurSimplifieeForm(
        request.POST or None,
        superviseur=superviseur   
    )

    if form.is_valid():
        with transaction.atomic():

            agent = form.cleaned_data['agent']
            affectation = form.cleaned_data['affectation']
            quantite = form.cleaned_data['quantite']

            # 🔒 sécurité agent
            if agent.superviseur != superviseur:
                raise ValidationError("Agent non autorisé")

            # 🔒 sécurité affectation
            if affectation.superviseur != superviseur:
                raise ValidationError("Affectation invalide")

            # 🔒 stock (double check backend)
            if quantite > affectation.quantite_restante:
                raise ValidationError("Stock insuffisant")

            produit = affectation.lot.produit

            # =========================
            # 1. PRIX
            # =========================
            if agent.type_agent == 'agent_gros':
                prix = affectation.prix_gros
                type_vente = 'gros'
            else:
                prix = affectation.prix_detail
                type_vente = 'detail'

            # =========================
            # 2. DISTRIBUTION AUTO
            # =========================
            distribution = DistributionAgent.objects.create(
                superviseur=superviseur,
                agent_terrain=agent,
                type_distribution='TERRAIN',
                quantite_totale=quantite

            )

            detail = DetailDistribution.objects.create(
                distribution=distribution,
                lot=affectation.lot,
                quantite=quantite,
                prix_gros=affectation.prix_gros,
                prix_detail=affectation.prix_detail
            )

            # =========================
            # 3. VENTE
            # =========================
            vente = Vente.objects.create(
                agent=agent,
                detail_distribution=detail,
                quantite=quantite,
                prix_vente_unitaire=prix,
                type_vente=type_vente,
                date_vente=timezone.now()
            )

            # =========================
            # 4. RECOUVREMENT AUTO
            # =========================
            montant = quantite * prix

            Recouvrement.objects.create(
                agent=agent,
                superviseur=superviseur,
                montant_recouvre=montant,
                date_recouvrement=timezone.now()
            )

            # =========================
            # 5. MAJ STOCK
            # =========================
            affectation.quantite_restante -= quantite
            affectation.save()

        messages.success(request, "✅ Vente enregistrée ")
        return redirect('tableau_de_bord_superviseur')

    return render(
        request,
        'agents/superviseur/vente_all_superviseur.html',
        {'form': form}
    )


@login_required
def liste_agents_sup(request):
    """
    Liste STRICTE des agents terrain sous la responsabilité
    du superviseur connecté
    """
    superviseur = request.user.agent

    if not superviseur.est_superviseur:
        return redirect('access_denied')

    # 🔒 FILTRAGE CLÉ
    agents = Agent.objects.filter(
        type_agent__in=['terrain', 'agent_gros'],
        superviseur=superviseur
    ).select_related('user')

    # =========================
    # AGENTS ACTIFS / INACTIFS
    # =========================
    agents_actifs = agents.filter(est_actif=True)
    agents_inactifs = agents.filter(est_actif=False)

    context = {
        'agents': agents,
        'agents_actifs': agents_actifs,
        'agents_inactifs': agents_inactifs,
        'agents_terrain': agents_actifs.order_by('user__first_name'),
    }

    return render(
        request,
        'agents/superviseur/liste_agents.html',
        context
    )



@login_required
def detail_agent_sup(request, agent_id):
    # =========================
    # SÉCURITÉ
    # =========================
    superviseur = request.user.agent

    if not superviseur.est_superviseur:
        return redirect("access_denied")

    agent = get_object_or_404(
        Agent.objects.select_related("user"),
        id=agent_id,
        superviseur=superviseur,
        type_agent__in=["terrain", "agent_gros"],
    )

    # =========================
    # AGRÉGATS FINANCIERS GLOBAUX
    # =========================
    total_ventes = agent.total_ventes or Decimal("0.00")
    total_recouvre = agent.total_recouvre or Decimal("0.00")
    argent_en_possession = agent.argent_en_possession or Decimal("0.00")

    # =========================
    # VENTES PAR TYPE
    # =========================
    ventes_par_type = (
        Vente.objects
        .filter(agent=agent)
        .values("type_vente")
        .annotate(
            total=Coalesce(
                Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                Decimal("0.00")
            )
        )
    )

    ventes_gros = Decimal("0.00")
    ventes_detail = Decimal("0.00")

    for v in ventes_par_type:
        if v["type_vente"] == "gros":
            ventes_gros = v["total"]
        elif v["type_vente"] == "detail":
            ventes_detail = v["total"]

    # =========================
    # POURCENTAGES & TAUX
    # =========================
    taux_recouvrement = Decimal("0.0")
    pourcentage_gros = Decimal("0.0")
    pourcentage_detail = Decimal("0.0")

    if total_ventes > 0:
        taux_recouvrement = (total_recouvre / total_ventes) * 100
        pourcentage_gros = (ventes_gros / total_ventes) * 100
        pourcentage_detail = (ventes_detail / total_ventes) * 100

    # =========================
    # DERNIÈRES VENTES
    # =========================
    dernieres_ventes = (
        Vente.objects
        .filter(agent=agent)
        .select_related(
            "client",
            "detail_distribution__lot__produit"
        )
        .order_by("-date_vente")[:10]
    )

    # =========================
    # STATS TEMPORELLES
    # =========================
    ventes_total_count = Vente.objects.filter(agent=agent).count()

    date_30j = timezone.now() - timedelta(days=30)
    ventes_30j_count = Vente.objects.filter(
        agent=agent,
        date_vente__gte=date_30j
    ).count()

    # =========================
    # CONTEXT
    # =========================
    context = {
        "agent": agent,

        # montants
        "total_ventes": total_ventes,
        "total_recouvre": total_recouvre,
        "argent_en_possession": argent_en_possession,

        # taux
        "taux_recouvrement": round(taux_recouvrement, 1),
        "pourcentage_gros": round(pourcentage_gros, 1),
        "pourcentage_detail": round(pourcentage_detail, 1),

        # ventes
        "ventes_gros": ventes_gros,
        "ventes_detail": ventes_detail,
        "ventes_total_count": ventes_total_count,
        "ventes_30j_count": ventes_30j_count,

        # listing
        "dernieres_ventes": dernieres_ventes,

        # actions
        "peut_recouvrir": argent_en_possession > 0,
    }

    return render(
        request,
        "agents/superviseur/detail_agent.html",
        context
    )

@login_required
def creer_agent(request):
    agent_connecte = request.user.agent

    # =========================
    # CHOIX DU FORMULAIRE
    # =========================

    if agent_connecte.est_superviseur:
        # Superviseur → Agent terrain uniquement
        form = SupervisorTerrainAgentCreationForm(
            request.POST or None,
            superviseur=agent_connecte
        )

    elif agent_connecte.est_rot:
        # ROT → Superviseur uniquement
        form = RotSupervisorCreationForm(
            request.POST or None
        )


    else:
        return HttpResponseForbidden("Accès non autorisé")

    # =========================
    # SOUMISSION
    # =========================

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('liste_agents_sup')

    return render(request, 'agents/superviseur/creer_agent.html', {
        'form': form
    })

@login_required
def modifier_agent(request, agent_id):

    agent_cible = get_object_or_404(Agent, id=agent_id)
    agent_connecte = request.user.agent

    # sécurité périmètre
    if agent_connecte.est_superviseur and agent_cible.superviseur != agent_connecte:
        return HttpResponseForbidden()

    # sécurité type
    if not agent_cible.est_agent_vente:
        return HttpResponseForbidden()

    form = SupervisorTerrainAgentUpdateForm(
        request.POST or None,
        instance=agent_cible
    )

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "✅ Agent modifié avec succès")
        return redirect('liste_agents_sup')

    return render(request, 'agents/superviseur/creer_agent.html', {
        'form': form,
        'agent': agent_cible
    })


@login_required
def liste_distribution_sup(request):

    superviseur = (
        Agent.objects
        .select_related('user')
        .get(user=request.user)
    )

    if not superviseur.est_superviseur:
        return redirect('access_denied')

    distributions = (
        DistributionAgent.objects
        .filter(superviseur=superviseur)
        .select_related(
            'agent_terrain',
            'agent_terrain__user',
        )
        .prefetch_related(
            Prefetch(
                'detaildistribution_set',
                queryset=DetailDistribution.objects
                .select_related('lot', 'lot__produit')
            )
        )
        .order_by('-date_distribution')
    )

    # -------------------------
    # FILTRES (GET)
    # -------------------------
    agent_id = request.GET.get('agent')
    produit_id = request.GET.get('produit')
    lot_id = request.GET.get('lot')

    date_debut = parse_date(request.GET.get('date_debut')) if request.GET.get('date_debut') else None
    date_fin = parse_date(request.GET.get('date_fin')) if request.GET.get('date_fin') else None

    if agent_id:
        distributions = distributions.filter(agent_terrain_id=agent_id)

    if produit_id:
        distributions = distributions.filter(
            detaildistribution__lot__produit_id=produit_id
        ).distinct()

    if lot_id:
        distributions = distributions.filter(
            detaildistribution__lot_id=lot_id
        ).distinct()

    if date_debut:
        distributions = distributions.filter(date_distribution__date__gte=date_debut)

    if date_fin:
        distributions = distributions.filter(date_distribution__date__lte=date_fin)
    
    agents = (
        Agent.objects
        .filter(superviseur=superviseur, est_actif=True)
        .select_related('user')
        .order_by('user__last_name')
    )

    produits = (
        Produit.objects
        .filter(lots__detaildistribution__distribution__superviseur=superviseur)
        .distinct()
        .order_by('nom')
    )
    
    lots = (
        LotEntrepot.objects
        .filter(
            detaildistribution__distribution__superviseur=superviseur
        )
        .select_related('produit', 'fournisseur') 
        .distinct()
        .order_by('produit__nom', '-date_reception')

    )
    
    paginator = Paginator(distributions, 10)  # 10 par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    query_params = request.GET.copy()
    query_params.pop('page', None)

    query_string = urlencode({
        k: v for k, v in query_params.items()
        if v not in [None, '', 'None']
    })

    context = {
        'distributions': page_obj,   
        'page_obj': page_obj,
        'query_string': query_string,

        'agents': agents,
        'produits': produits,
        'lots': lots,

        'filters': {
            'agent': agent_id,
            'produit': produit_id,
            'lot': lot_id,
            'date_debut': date_debut,
            'date_fin': date_fin,
        }
    }

    return render(
        request,
        'agents/superviseur/liste_distributions.html',
        context
    )

####

########""
#rot -> supperviseur
@login_required
def affecter_lot_superviseur(request):
    agent = request.user.agent

    if not agent.est_rot:
        return redirect('access_denied')

    if request.method == 'POST':
        form = RotAffectationLotSuperviseurForm(request.POST, rot=agent)
        
        if form.is_valid():
            affectation = form.save()

            lot = affectation.lot
            quantite = affectation.quantite_initiale

            message = (
                f"✅ {quantite} unité(s) de {lot.produit.nom} "
                f"affectée(s) à {affectation.superviseur.full_name}"
            )

            messages.success(request, message)
            return redirect('rot_affectations_liste')

    else:
        form = RotAffectationLotSuperviseurForm(rot=agent)

    context = {
        'form': form,
        'page_title': 'Affecter un lot',
    }
    
    return render(request, 'agents/rot/affecter_lot.html', context)


from django.utils.dateparse import parse_date
from django.db.models import Sum
from django.contrib.auth.decorators import login_required

@login_required
def rot_affectations_liste(request):
    agent = request.user.agent

    if not agent.est_rot:
        return redirect('access_denied')

    affectations = (
        AffectationLotSuperviseur.objects
        .filter(attribue_par=agent)
        .select_related(
            'lot__produit',
            'lot__fournisseur',
            'superviseur__user'
        )
       .order_by('-lot__date_reception', '-date_affectation')

    )


    # --------------------
    # FILTRES (GET)
    # --------------------
    date_debut = safe_parse_date(request.GET.get('date_debut'))
    date_fin = safe_parse_date(request.GET.get('date_fin'))

    lot_id = request.GET.get('lot')
    fournisseur_id = request.GET.get('fournisseur')

    if date_debut:
        affectations = affectations.filter(
            date_affectation__gte=date_debut
        )

    if date_fin:
        affectations = affectations.filter(
            date_affectation__lte=date_fin
        )

    if lot_id:
        affectations = affectations.filter(lot_id=lot_id)

    if fournisseur_id:
        affectations = affectations.filter(
            lot__fournisseur_id=fournisseur_id
        )
    # =========================
    # PAGINATION
    # =========================
    paginator = Paginator(affectations, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # =========================
    # QUERY STRING PROPRE
    # =========================
    query_params = request.GET.copy()
    query_params.pop('page', None)

    query_string = urlencode({
        k: v for k, v in query_params.items()
        if v not in [None, '', 'None']
    })

    # --------------------
    # STATS (post-filtre)
    # --------------------
    total_quantite = affectations.aggregate(
        total=Sum('quantite_initiale')
    )['total'] or 0

    superviseurs_count = affectations.values('superviseur').distinct().count()
    produits_count = affectations.values('lot__produit').distinct().count()

    context = {
        'affectations': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,

        'affectations_total': {
            'quantite': total_quantite,
        },
        'superviseurs_count': superviseurs_count,
        'produits_count': produits_count,

        'lots': LotEntrepot.objects
            .select_related('produit', 'fournisseur')
            .order_by('-date_reception'),

        'fournisseurs': Fournisseur.objects.all(),

        'filtres': {
            'date_debut': date_debut,
            'date_fin': date_fin,
            'lot': lot_id,
            'fournisseur': fournisseur_id,
        }
    }
    return render(
        request,
        'agents/rot/affectations_liste.html',
        context
    )




@login_required
def liste_agents_rot(request):
    agent_connecte = request.user.agent

    if not agent_connecte.est_rot:
        return redirect("access_denied")

    # 🔹 Superviseurs actifs
    superviseurs = (
        Agent.objects
        .filter(type_agent="entrepot", est_actif=True)
        .prefetch_related(
            Prefetch(
                "agents_geres",
                queryset=Agent.objects.filter(
                    type_agent__in=["terrain", "agent_gros"],
                    est_actif=True
                )
            )
        )
        .select_related("user")
    )

    context = {
        "superviseurs": superviseurs,
    }

    return render(
        request,
        "agents/rot/liste_agents.html",
        context
    )

@login_required
def detail_agent_rot(request, agent_id):
    agent_connecte = request.user.agent

    if not agent_connecte.est_rot:
        return redirect("access_denied")

    agent = get_object_or_404(
        Agent.objects.select_related("user", "superviseur"),
        id=agent_id
    )

    # 🔐 Sécurité scope ROT
    if agent.type_agent in ["terrain", "agent_gros"]:
        if not agent.superviseur or agent.superviseur.type_agent != "entrepot":
            return redirect("access_denied")

    if agent.type_agent not in ["entrepot", "terrain", "agent_gros"]:
        return redirect("access_denied")

    # 📊 Récupérer toutes les données via le service
    from agents.services.agent_data_service import AgentDataService
    context = AgentDataService.get_agent_complete_data(agent)

    return render(
        request,
        "agents/rot/detail_agent.html",
        context
    )




@login_required
def recouvrer_superviseur(request):
    rot = request.user.agent
    if not rot.est_rot:
        return redirect("access_denied")

    superviseur = None
    resume = None

    # ==========================
    # ÉTAPE 1 : lecture superviseur (GET)
    # ==========================
    superviseur_id = request.GET.get("superviseur")
    if superviseur_id:
        superviseur = Agent.objects.filter(
            id=superviseur_id,
            type_agent="entrepot",
            est_actif=True
        ).first()

        if superviseur:
            # 🔑 SOURCE DE VÉRITÉ
            resume = RotDashboardService.get_cash_superviseur_post_cloture(
                superviseur
            )

    # ==========================
    # ÉTAPE 2 : formulaire (POST)
    # ==========================
    if request.method == "POST":
        form = RecouvrementSuperviseurForm(request.POST)

        if form.is_valid():
            rec = form.save(commit=False)
            rec.rot = rot

            # 🔒 Sécurité comptable : pas plus que le cash restant
            if resume and rec.montant > resume["cash_restant"]:
                messages.error(
                    request,
                    "Montant supérieur au cash réellement disponible."
                )
            else:
                rec.save()
                messages.success(
                    request,
                    "Recouvrement enregistré avec succès."
                )
                return redirect(
                    f"{request.path}?superviseur={rec.superviseur_id}"
                )
    else:
        form = RecouvrementSuperviseurForm(
            initial={"superviseur": superviseur}
        )

    return render(
        request,
        "agents/rot/recouvrer_superviseur.html",
        {
            "form": form,
            "superviseur": superviseur,
            "resume": resume,
        }
    )
