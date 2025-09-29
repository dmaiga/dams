# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Agent,  Client,  Vente, Facture,LotEntrepot,DetailDistribution,DistributionAgent
from django.contrib.auth.models import User
from django.db import models 
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import VenteForm
from .models import Agent, Client, Vente
from decimal import Decimal
from django.db import transaction

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import models
from django.contrib import messages
from .models import Agent,  Client,  Vente, Produit
from .forms import DistributionForm, VenteForm,ReceptionLotForm
from django.db.models import Sum


# views.py - CORRIGE la view distribuer_stock
from django.db import transaction
from django.http import JsonResponse
import json
from decimal import Decimal
#=========
#DASHBOARD
#========
@login_required
def dashboard(request):
    """Tableau de bord principal avec les nouveaux modèles"""
    # Statistiques générales
    total_agents = Agent.objects.count()
    total_lots = LotEntrepot.objects.count()
    total_distributions = DistributionAgent.objects.count()
    
    # Calcul du stock total entrepôt
    total_stock_entrepot = LotEntrepot.objects.aggregate(
        total=models.Sum('quantite_restante')
    )['total'] or 0
    
    # Calcul de la valeur totale du stock
    valeur_stock_total = 0
    lots_avec_stock = LotEntrepot.objects.filter(quantite_restante__gt=0)
    for lot in lots_avec_stock:
        valeur_stock_total += lot.quantite_restante * lot.prix_achat_unitaire
    
    # Dernières activités
    dernieres_distributions = DistributionAgent.objects.all().order_by('-date_distribution')[:5]
    derniers_lots = LotEntrepot.objects.all().order_by('-date_reception')[:5]
    
    # Produits les plus distribués (top 5) - CORRIGÉ
    from django.db.models import Sum
    produits_populaires = DetailDistribution.objects.values(
        'lot__produit__nom'  # CORRECTION: lot__produit__nom au lieu de lot__produit_nom
    ).annotate(
        total_quantite=Sum('quantite')
    ).order_by('-total_quantite')[:5]
    
    # Stocks faibles (moins de 10 unités restantes)
    stocks_faibles = LotEntrepot.objects.filter(
        quantite_restante__gt=0, 
        quantite_restante__lt=10
    ).order_by('quantite_restante')[:5]
    
    # Agents les plus actifs (top 5)
    agents_actifs = DistributionAgent.objects.values(
        'agent_terrain__user__first_name',
        'agent_terrain__user__last_name'
    ).annotate(
        total_distributions=models.Count('id')
    ).order_by('-total_distributions')[:5]
    
    # Dernières ventes
    dernieres_ventes = Vente.objects.all().order_by('-date_vente')[:5]
    
    context = {
        # Statistiques principales
        'total_agents': total_agents,
        'total_lots': total_lots,
        'total_distributions': total_distributions,
        'total_stock_entrepot': total_stock_entrepot,
        'valeur_stock_total': valeur_stock_total,
        
        # Dernières activités
        'dernieres_distributions': dernieres_distributions,
        'derniers_lots': derniers_lots,
        'dernieres_ventes': dernieres_ventes,
        
        # Analytics
        'produits_populaires': produits_populaires,
        'stocks_faibles': stocks_faibles,
        'agents_actifs': agents_actifs,
        
        # Calculs pour les pourcentages
        'lots_avec_stock': lots_avec_stock.count(),
        'lots_epuises': LotEntrepot.objects.filter(quantite_restante=0).count(),
        'total_ventes': Vente.objects.count(),
    }
    
    return render(request, 'core/dashboard.html', context)

#=========
#AGENT
#========

@login_required
def liste_agents(request):
    """Liste tous les agents"""
    agents = Agent.objects.all()
    return render(request, 'core/agents/liste_agents.html', {'agents': agents})

@login_required
def creer_agent(request):
    """Créer un nouvel agent"""
    if request.method == 'POST':
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        telephone = request.POST.get('telephone')
        type_agent = request.POST.get('type_agent', 'terrain')
        
        # Créer l'utilisateur
        user = User.objects.create_user(
            username=telephone,
            password='temp123',  # Mot de passe temporaire
            first_name=nom,
            last_name=prenom
        )
        
        # Créer l'agent
        agent = Agent.objects.create(
            user=user,
            telephone=telephone,
            type_agent=type_agent
        )
        
        return redirect('liste_agents')
    
    return render(request, 'core/agents/creer_agent.html')

@login_required
def modifier_agent(request, agent_id):
    """Modifier un agent existant"""
    agent = get_object_or_404(Agent, id=agent_id)
    
    if request.method == 'POST':
        agent.user.first_name = request.POST.get('nom')
        agent.user.last_name = request.POST.get('prenom')
        agent.telephone = request.POST.get('telephone')
        agent.type_agent = request.POST.get('type_agent')
        
        agent.user.save()
        agent.save()
        
        return redirect('liste_agents')
    
    return render(request, 'core/agents/modifier_agent.html', {'agent': agent})

@login_required
def supprimer_agent(request, agent_id):
    """Supprimer un agent"""
    agent = get_object_or_404(Agent, id=agent_id)
    
    if request.method == 'POST':
        # Supprimer l'utilisateur associé
        agent.user.delete()
        return redirect('liste_agents')
    
    return render(request, 'core/agents/supprimer_agent.html', {'agent': agent})

#========
#ENTREPOT
#========

# views.py
@login_required
def reception_lot(request):
    if request.method == 'POST':
        form = ReceptionLotForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                lot = form.save()
                messages.success(request, f"Lot {lot.reference_lot} réceptionné avec succès!")
                return redirect('liste_lots')
            except Exception as e:
                messages.error(request, f"Erreur lors de l'enregistrement: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ReceptionLotForm()
    
    return render(request, 'core/entrepot/reception_lot.html', {
        'form': form
    })

@login_required
def liste_lots(request):
    """Liste tous les lots avec leurs informations"""
    lots = LotEntrepot.objects.all().order_by('-date_reception')
    
    # Filtres
    produit_filter = request.GET.get('produit')
    fournisseur_filter = request.GET.get('fournisseur')
    statut_filter = request.GET.get('statut')
    
    if produit_filter:
        lots = lots.filter(produit__nom__icontains=produit_filter)
    
    if fournisseur_filter:
        lots = lots.filter(fournisseur__nom__icontains=fournisseur_filter)
    
    if statut_filter:
        if statut_filter == 'disponible':
            lots = lots.filter(quantite_restante__gt=0)
        elif statut_filter == 'epuise':
            lots = lots.filter(quantite_restante=0)
    
    # Calcul de la valeur totale
    total_valeur = 0
    for lot in lots:
        total_valeur += lot.quantite_restante * lot.prix_achat_unitaire
    
    context = {
        'lots': lots,
        'total_lots': lots.count(),
        'total_stock': lots.aggregate(total=models.Sum('quantite_restante'))['total'] or 0,
        'total_valeur': total_valeur,
    }
    
    return render(request, 'core/entrepot/liste_lots.html', context)


#============
#DISTRIBUTION
#============
# views.py
@login_required
def distribuer_produits_agent(request):
    if request.method == 'POST':
        form = DistributionForm(request.POST, current_user=request.user)
        if form.is_valid():
            try:
                distribution = form.save()
                messages.success(request, f"Distribution #{distribution.id} créée avec succès!")
                return redirect('liste_distributions')
            except Exception as e:
                messages.error(request, f"Erreur lors de la distribution: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = DistributionForm(current_user=request.user)
    
    return render(request, 'core/distribution/distribuer.html', {
        'form': form
    })

def liste_distributions(request):
    """Liste toutes les distributions"""
    distributions = DistributionAgent.objects.all().order_by('-date_distribution')
    
    # Filtres
    agent_filter = request.GET.get('agent')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    if agent_filter:
        distributions = distributions.filter(agent_terrain__user__first_name__icontains=agent_filter)
    
    if date_debut:
        distributions = distributions.filter(date_distribution__date__gte=date_debut)
    
    if date_fin:
        distributions = distributions.filter(date_distribution__date__lte=date_fin)
    
    # Calcul des quantités totales distribuées
    for distribution in distributions:
        distribution.quantite_totale = sum(detail.quantite for detail in distribution.detaildistribution_set.all())
    
    context = {
        'distributions': distributions,
        'total_distributions': distributions.count(),
    }
    
    return render(request, 'core/distribution/liste_distributions.html', context)

def detail_distribution(request, distribution_id):
    """Détail d'une distribution spécifique"""
    distribution = get_object_or_404(DistributionAgent, id=distribution_id)
    details = distribution.detaildistribution_set.all()
    
    # Calcul de la quantité totale
    quantite_totale = sum(detail.quantite for detail in details)
    
    context = {
        'distribution': distribution,
        'details': details,
        'quantite_totale': quantite_totale,
    }
    
    return render(request, 'core/distribution/detail_distribution.html', context)

# API pour récupérer le stock d'un produit
def get_stock_produit(request, produit_id):
    """API pour récupérer le stock d'un produit (AJAX)"""
    try:
        produit = Produit.objects.get(id=produit_id)
        lots_disponibles = LotEntrepot.get_lots_disponibles(produit.nom)
        stock_total = sum(lot.quantite_restante for lot in lots_disponibles)
        
        # Informations sur les lots disponibles
        lots_info = []
        for lot in lots_disponibles:
            lots_info.append({
                'reference': lot.reference_lot or f"Lot#{lot.id}",
                'quantite_restante': lot.quantite_restante,
                'prix_achat': float(lot.prix_achat_unitaire),
                'date_reception': lot.date_reception.strftime('%d/%m/%Y')
            })
        
        return JsonResponse({
            'stock': stock_total,
            'produit': produit.nom,
            'lots_disponibles': lots_info
        })
    except Produit.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé'}, status=404)


#=====
#VENTE
#=====
# views.py
@login_required
def enregistrer_vente(request):
    """Enregistrer une vente - VUE CORRIGÉE"""
    try:
        # Récupérer l'agent connecté (doit être agent terrain)
        agent = Agent.objects.get(user=request.user, type_agent='terrain')
    except Agent.DoesNotExist:
        messages.error(request, "Vous devez être un agent terrain pour effectuer des ventes.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = VenteForm(request.POST, agent=agent)
        if form.is_valid():
            try:
                vente = form.save()
                messages.success(request, 
                    f"Vente enregistrée ! {vente.quantite} {vente.detail_distribution.lot.produit.nom} "
                    f"vendu à {vente.client.nom} pour {vente.prix_vente_unitaire * vente.quantite} FCFA"
                )
                return redirect('liste_ventes')
            except Exception as e:
                messages.error(request, f"Erreur lors de l'enregistrement: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = VenteForm(agent=agent)
    
    return render(request, 'core/ventes/enregistrer_vente.html', {
        'form': form,
        'agent': agent
    })

@login_required
def liste_ventes(request):
    """Lister toutes les ventes"""
    # Si c'est un agent terrain, ne voir que ses ventes
    if hasattr(request.user, 'agent') and request.user.agent.type_agent == 'terrain':
        ventes = Vente.objects.filter(agent=request.user.agent).order_by('-date_vente')
    else:
        # Sinon (superviseur/admin), voir toutes les ventes
        ventes = Vente.objects.all().order_by('-date_vente')
    
    # Calcul du chiffre d'affaires total
    chiffre_affaires_total = sum(vente.quantite * vente.prix_vente_unitaire for vente in ventes)
    
    context = {
        'ventes': ventes,
        'chiffre_affaires_total': chiffre_affaires_total,
        'total_ventes': ventes.count(),
    }
    
    return render(request, 'core/ventes/liste_ventes.html', context)

# API pour récupérer les informations d'un détail de distribution
def get_info_distribution(request, detail_id):
    """API pour récupérer les infos d'un détail de distribution"""
    try:
        detail = DetailDistribution.objects.get(id=detail_id)
        
        return JsonResponse({
            'produit': detail.lot.produit.nom,
            'quantite_disponible': detail.quantite,
            'prix_gros': float(detail.prix_gros) if detail.prix_gros else None,
            'prix_detail': float(detail.prix_detail) if detail.prix_detail else None,
            'reference_lot': detail.lot.reference_lot or f"Lot#{detail.lot.id}",
        })
    except DetailDistribution.DoesNotExist:
        return JsonResponse({'error': 'Distribution non trouvée'}, status=404)