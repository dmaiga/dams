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
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
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
    Recouvrement,VersementBancaire,VersementBancaire,RecuVersement
)

# Project forms
from core.forms import (
    FactureLotForm, VenteForm, DistributionForm, ReceptionLotForm, 
    DetteForm, PaiementDetteForm, DistributionSuppressionForm,
    DistributionModificationForm,RecouvrementForm,
    FournisseurForm,VersementForm

)

from agents.forms import (
                           
                            SupervisorTerrainAgentCreationForm,
                            
                            DirectionAgentCreationForm,
                            RotSupervisorCreationForm,
                            
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

from agents.services.rot_service import RotDashboardService


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


# agents/views/rot_views.py
@login_required
def tableau_de_bord_rot(request):
    """
    Tableau de bord du ROT (Responsable Opérations et Trésorerie)
    """
    try:
        context = RotDashboardService.build_dashboard_rot(request.user)
    except Exception as e:
        # Gestion d'erreur pour debug
        print(f"Erreur dans tableau_de_bord_rot: {e}")
        context = None
    
    if not context:
        messages.error(request, "Accès réservé aux responsables ROT")
        return redirect('login')
    
    return render(request, 'agents/dashboards/rot.html', context)