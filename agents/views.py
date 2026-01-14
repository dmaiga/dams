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
# DB / ORM
from django.db import models, transaction
from django.db.models import (
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField,Prefetch
)
from django.db.models.functions import Coalesce

from django import forms
from django.core.exceptions import ValidationError 
from django.utils import timezone
from datetime import timedelta
# Python stdlib
from datetime import timedelta
from decimal import Decimal
import json

# Project models
from core.models import (
    Agent, Client, Vente, Produit,Depense,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,
    Recouvrement,VersementBancaire,VersementBancaire,RecuVersement,
    AffectationLotSuperviseur
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
                            RecouvrementSuperviseurForm
                            
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
from agents.services.agent_data_service import AgentDataService


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

    context = RotDashboardService.build_dashboard()

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
@login_required
def superviseur_lots_affectes(request):
    agent = request.user.agent

    if not agent.est_superviseur:
        return redirect('access_denied')

    lots_affectes = (
        AffectationLotSuperviseur.objects
        .filter(superviseur=agent, quantite_restante__gt=0)
        .select_related(
            'lot__produit',
            'attribue_par__user'
        )
        .order_by('-date_affectation')
    )
    
    # Préparer les données pour le template
    lots_data = []
    for affectation in lots_affectes:
        # Calculer le taux d'utilisation pour chaque lot
        taux_restant = 0
        taux_utilise = 0
        if affectation.quantite_initiale > 0:
            taux_restant = (affectation.quantite_restante / affectation.quantite_initiale) * 100
            taux_utilise = 100 - taux_restant
        
        # Convertir en unités si produit conditionné
        quantite_initiale_unites = None
        quantite_restante_unites = None
        if affectation.lot.est_conditionne and affectation.lot.produit.poids_unitaire_kg:
            poids = affectation.lot.produit.poids_unitaire_kg
            quantite_initiale_unites = affectation.quantite_initiale / poids
            quantite_restante_unites = affectation.quantite_restante / poids
        
        lots_data.append({
            'affectation': affectation,
            'taux_restant': round(taux_restant, 1),
            'taux_utilise': round(taux_utilise, 1),
            'quantite_initiale_unites': quantite_initiale_unites,
            'quantite_restante_unites': quantite_restante_unites,
            'statut_progress': 'success' if taux_restant > 50 else 'warning' if taux_restant > 20 else 'danger',
        })
    
    # Calculer les totaux
    total_kg_initial = sum(a.quantite_initiale for a in lots_affectes)
    total_kg_restant = sum(a.quantite_restante for a in lots_affectes)
    taux_utilisation_global = 0
    if total_kg_initial > 0:
        taux_utilisation_global = ((total_kg_initial - total_kg_restant) / total_kg_initial) * 100

    context = {
        'lots_data': lots_data,
        'total_kg_initial': total_kg_initial,
        'total_kg_restant': total_kg_restant,
        'taux_utilisation_global': round(taux_utilisation_global, 1),
        'nombre_lots': len(lots_data),
    }

    return render(request, 'agents/superviseur/lots_affectes.html', context)


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
    superviseur = request.user.agent

    if not superviseur.est_superviseur:
        return redirect('access_denied')

    # 🔒 L'agent DOIT appartenir à ce superviseur
    agent = get_object_or_404(
        Agent.objects.select_related('user'),
        id=agent_id,
        superviseur=superviseur,
        type_agent__in=['terrain', 'agent_gros']
    )

    # Données essentielles uniquement
    total_ventes = agent.total_ventes or Decimal('0')
    total_recouvre = agent.total_recouvre or Decimal('0')
    argent_en_possession = agent.argent_en_possession or Decimal('0')
    
    # Calcul du taux de recouvrement
    taux_recouvrement = 0
    pourcentage_gros = 0
    pourcentage_detail = 0
    if total_ventes > 0:
        taux_recouvrement = (total_recouvre / total_ventes) * 100
        pourcentage_gros = (ventes_gros / total_ventes) * 100
        pourcentage_detail = (ventes_detail / total_ventes) * 100

    # 5 dernières ventes avec plus d'informations
    from django.db.models import F, DecimalField, Sum
    from django.db.models.functions import Coalesce
    
    dernieres_ventes = Vente.objects.filter(
        agent=agent
    ).select_related(
        'client',
        'detail_distribution__lot__produit'
    ).order_by('-date_vente')[:5]

    # Calculer le total des ventes par type (gros/détail)
    ventes_gros = Vente.objects.filter(
        agent=agent,
        type_vente='gros'
    ).aggregate(
        total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0'))
    )['total'] or Decimal('0')
    
    ventes_detail = Vente.objects.filter(
        agent=agent,
        type_vente='detail'
    ).aggregate(
        total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0'))
    )['total'] or Decimal('0')

    # Nombre total de ventes
    ventes_total_count = Vente.objects.filter(agent=agent).count()

    # Statistiques 30 derniers jours
    from datetime import timedelta
    date_30j = timezone.now() - timedelta(days=30)
    ventes_30j_count = Vente.objects.filter(
        agent=agent,
        date_vente__gte=date_30j
    ).count()

    context = {
        'agent': agent,
        'total_ventes': total_ventes,
        'total_recouvre': total_recouvre,
        'argent_en_possession': argent_en_possession,
        'taux_recouvrement': round(taux_recouvrement, 1),
        'pourcentage_gros': round(pourcentage_gros, 1),
        'pourcentage_detail': round(pourcentage_detail, 1),
        'ventes_gros': ventes_gros,
        'ventes_detail': ventes_detail,
        'ventes_total_count': ventes_total_count,
        'ventes_30j_count': ventes_30j_count,
        'dernieres_ventes': dernieres_ventes,
        'peut_recouvrir': argent_en_possession > 0,
    }

    return render(
        request,
        'agents/superviseur/detail_agent.html',
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

    # Sécurité minimale
    if agent_connecte.est_superviseur and agent_cible.superviseur != agent_connecte:
        return HttpResponseForbidden()

    form = SupervisorTerrainAgentCreationForm(
        request.POST or None,
        instance=agent_cible,
        superviseur=agent_connecte if agent_connecte.est_superviseur else None
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
        .filter(superviseur=superviseur)  # 🔑 inclut AUTO + agent_gros
        .select_related(
            'agent_terrain',
            'agent_terrain__user',
        )
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

    return render(
        request,
        'agents/superviseur/liste_distributions.html',
        {'distributions': distributions}
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
            try:
                affectation = form.save()
                
                # Message adapté selon le type de produit
                lot = affectation.lot
                quantite_saisie = form.cleaned_data['quantite_saisie']
                
                if lot.est_conditionne:
                    poids_unitaire = lot.produit.poids_unitaire_kg
                    quantite_kg = quantite_saisie * poids_unitaire
                    message = (
                        f"✅ {quantite_saisie} unité(s) ({quantite_kg} kg) de "
                        f"{lot.produit.nom} affecté(s) à {affectation.superviseur.full_name}"
                    )
                else:
                    message = (
                        f"✅ {quantite_saisie} kg de {lot.produit.nom} "
                        f"affecté(s) à {affectation.superviseur.full_name}"
                    )
                
                messages.success(request, message)
                return redirect('rot_affectations_liste')
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'affectation: {str(e)}")
    else:
        form = RotAffectationLotSuperviseurForm(rot=agent)

    context = {
        'form': form,
        'page_title': 'Affecter un lot',
    }
    
    return render(request, 'agents/rot/affecter_lot.html', context)



@login_required
def rot_affectations_liste(request):
    agent = request.user.agent

    if not agent.est_rot:
        return redirect('access_denied')

    # Affectations faites par le ROT
    affectations = (
        AffectationLotSuperviseur.objects
        .filter(attribue_par=agent)
        .select_related(
            'lot__produit',
            'lot__fournisseur',
            'superviseur__user'
        )
        .order_by('-date_affectation')
    )

    # Statistiques simples et cohérentes
    total_quantite = affectations.aggregate(
        total=Sum('quantite_initiale')
    )['total'] or 0

    superviseurs_count = affectations.values('superviseur').distinct().count()
    produits_count = affectations.values('lot__produit').distinct().count()

    context = {
        'affectations': affectations,
        'affectations_total': {
            'quantite': total_quantite,
        },
        'superviseurs_count': superviseurs_count,
        'produits_count': produits_count,
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

    form = RecouvrementSuperviseurForm(
        request.POST or None,
        rot=rot
    )

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(
            request,
            "✅ Recouvrement superviseur enregistré avec succès"
        )
        return redirect("dashboard_rot")

    return render(
        request,
        "agents/rot/recouvrer_superviseur.html",
        {"form": form}
    )
