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
    FactureLotForm, VenteForm, DistributionForm, ReceptionLotForm, 
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
        .filter(superviseur=agent)
        .select_related(
            'lot',
            'lot__produit',
            'attribue_par'
        )
        .order_by('-date_affectation')
    )

    return render(request, 'agents/superviseur/lots_affectes.html', {
        'lots_affectes': lots_affectes
    })


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
        type_agent='terrain',
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

    # 🔒 L’agent DOIT appartenir à ce superviseur
    agent = get_object_or_404(
        Agent,
        id=agent_id,
        superviseur=superviseur,
        type_agent='terrain'
    )

    # =========================
    # DONNÉES MÉTIER
    # =========================
    ventes = Vente.objects.filter(agent=agent).order_by('-date_vente')

    ventes_gros = ventes.filter(type_vente='gros')
    ventes_detail = ventes.filter(type_vente='detail')

    total_ventes_gros = sum(v.total_vente for v in ventes_gros)
    total_ventes_detail = sum(v.total_vente for v in ventes_detail)

    recouvrements = Recouvrement.objects.filter(
        agent=agent
    ).order_by('-date_recouvrement')[:5]

    date_limite = timezone.now() - timedelta(days=30)
    ventes_recentes = ventes.filter(date_vente__gte=date_limite)

    context = {
        'agent': agent,
        'ventes': ventes[:10],
        'ventes_total_count': ventes.count(),
        'total_ventes': agent.total_ventes,
        'total_recouvre': agent.total_recouvre,
        'argent_en_possession': agent.argent_en_possession,
        'total_ventes_gros': total_ventes_gros,
        'total_ventes_detail': total_ventes_detail,
        'recouvrements': recouvrements,
        'ventes_recentes_count': ventes_recentes.count(),
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
    superviseur = request.user.agent

    if not superviseur.est_superviseur:
        return redirect('access_denied')

    distributions = (
        DistributionAgent.objects
        .filter(superviseur=superviseur)
        .select_related('agent_terrain')
        .prefetch_related(
            'detaildistribution_set__lot__produit'
        )
        .order_by('-date_distribution')
    )

    context = {
        'distributions': distributions,
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

    form = RotAffectationLotSuperviseurForm(
        request.POST or None,
        rot=agent
    )

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "✅ Lot affecté au superviseur avec succès")
        return redirect('rot_affectations_liste')

    return render(request, 'agents/rot/affecter_lot.html', {
        'form': form
    })

@login_required
def rot_affectations_liste(request):
    agent = request.user.agent

    if not agent.est_rot:
        return redirect('access_denied')

    affectations = (
        AffectationLotSuperviseur.objects
        .filter(attribue_par=agent)
        .select_related('lot', 'superviseur', 'lot__produit')
        .order_by('-date_affectation')
    )

    return render(request, 'agents/rot/affectations_liste.html', {
        'affectations': affectations
    })

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
                    type_agent="terrain",
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
    if agent.type_agent == "terrain":
        if not agent.superviseur or agent.superviseur.type_agent != "entrepot":
            return redirect("access_denied")

    if agent.type_agent not in ["entrepot", "terrain"]:
        return redirect("access_denied")

    context = {
        "agent": agent,
    }

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
