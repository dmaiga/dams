# Django imports
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


from django.utils import timezone
from datetime import timedelta
# Python stdlib
from datetime import timedelta
from decimal import Decimal
import json

# Project models
from .models import (
    Agent, Client, Vente, Produit, Facture,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,Recouvrement
)

# Project forms
from .forms import (
    VenteForm, DistributionForm, ReceptionLotForm, FactureForm,
    DetteForm, PaiementDetteForm, DistributionSuppressionForm,
    DistributionModificationForm,UploadFactureForm,RecouvrementForm,
    FournisseurForm
)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages




def custom_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Vérifier si l'utilisateur est un agent
            try:
                agent = Agent.objects.get(user=user)
                if agent.type_agent == "direction": 
                    return redirect("dashboard")  # Tableau de bord admin
                elif agent.type_agent == "entrepot": 
                    return redirect("tableau_de_bord_superviseur")
                elif agent.type_agent == "terrain":  
                    return redirect("dashboard_agent")
            except Agent.DoesNotExist:
                # Pas un agent → tableau générique ou admin Django
                if user.is_staff or user.is_superuser:
                    return redirect("admin:index")  # Admin Django
                else:
                    return redirect("dashboard")  # Tableau de bord générique
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    else:
        form = AuthenticationForm()

    return render(request, "registration/login.html", {"form": form})

def logout_user(request):
    logout(request)  
    return redirect('login') 

#=========
#AGENT
#========
# views.py
@login_required
def dashboard_agent(request):
    """Tableau de bord pour les agents terrain"""
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    # Récupérer ou créer le bonus agent
    bonus_agent, created = BonusAgent.objects.get_or_create(agent=agent)
    
    # Calcul des indicateurs
    ventes = Vente.objects.filter(agent=agent)
    ventes_mois = ventes.filter(date_vente__month=timezone.now().month)
    ventes_comptant_mois = ventes_mois.filter(mode_paiement='comptant')
    ventes_credit_mois = ventes_mois.filter(mode_paiement='credit')
    
    # Chiffre d'affaires
    chiffre_affaires_total = sum(vente.total_vente for vente in ventes)
    chiffre_affaires_mois = sum(vente.total_vente for vente in ventes_mois)
    
    # Dettes
    dettes_en_cours = Dette.objects.filter(
        vente__agent=agent,
        statut__in=['en_cours', 'partiellement_paye', 'en_retard']
    )
    total_a_recouvrer = sum(dette.montant_restant for dette in dettes_en_cours)
    
    # Dettes prioritaires (en retard ou échéance proche)
    dettes_prioritaires = dettes_en_cours.order_by('date_echeance')[:5]
    
    # Stock disponible
    produits_disponibles = DetailDistribution.objects.filter(
        distribution__agent_terrain=agent,
        quantite__gt=0
    ).select_related('lot', 'lot__produit')
    total_stock_disponible = sum(detail.quantite for detail in produits_disponibles)
    
    # Statistiques bonus
    mois_courant = timezone.now().month
    annee_courante = timezone.now().year
    produits_recouverts_mois = bonus_agent.get_produits_recouverts_par_mois(mois_courant, annee_courante)
    bonus_mois = produits_recouverts_mois * 100
    
    # Clients servis ce mois
    clients_servis_mois = ventes_mois.values('client').distinct().count()
    
    # Activité récente
    ventes_recentes = ventes.select_related(
        'client', 'detail_distribution__lot__produit'
    ).order_by('-date_vente')[:5]
    
    # Calcul de la croissance (exemple simplifié)
    ventes_mois_dernier = ventes.filter(
        date_vente__month=timezone.now().month-1 if timezone.now().month > 1 else 12,
        date_vente__year=timezone.now().year if timezone.now().month > 1 else timezone.now().year-1
    )
    ca_mois_dernier = sum(vente.total_vente for vente in ventes_mois_dernier)
    
    if ca_mois_dernier > 0:
        pourcentage_croissance = ((chiffre_affaires_mois - ca_mois_dernier) / ca_mois_dernier) * 100
    else:
        pourcentage_croissance = 100 if chiffre_affaires_mois > 0 else 0
    
    context = {
        'agent': agent,
        'bonus_agent': bonus_agent,
        'chiffre_affaires_total': chiffre_affaires_total,
        'chiffre_affaires_mois': chiffre_affaires_mois,
        'total_a_recouvrer': total_a_recouvrer,
        'dettes_en_cours': dettes_en_cours,
        'dettes_prioritaires': dettes_prioritaires,
        'produits_disponibles': produits_disponibles,
        'total_stock_disponible': total_stock_disponible,
        'produits_recouverts_mois': produits_recouverts_mois,
        'bonus_mois': bonus_mois,
        'ventes_mois': ventes_mois,
        'ventes_comptant_mois': ventes_comptant_mois,
        'ventes_credit_mois': ventes_credit_mois,
        'clients_servis_mois': clients_servis_mois,
        'ventes_recentes': ventes_recentes,
        'pourcentage_croissance': round(pourcentage_croissance, 1),
    }
    
    return render(request, 'core/dashboard/dashboard_agent.html', context)

@login_required
def liste_agents(request):
    """Liste uniquement les agents terrain et superviseurs"""
    agents = Agent.objects.filter(type_agent__in=['entrepot', 'terrain'])
    return render(request, 'core/agents/liste_agents.html', {'agents': agents})



@login_required
def detail_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    
    # Récupérer les statistiques des ventes
    ventes = Vente.objects.filter(agent=agent).order_by('-date_vente')
    total_ventes = agent.total_ventes
    total_recouvre = agent.total_recouvre
    argent_en_possession = agent.argent_en_possession
    
    # Statistiques par type de vente
    ventes_gros = ventes.filter(type_vente='gros')
    ventes_detail = ventes.filter(type_vente='detail')
    
    total_ventes_gros = sum(vente.total_vente for vente in ventes_gros)
    total_ventes_detail = sum(vente.total_vente for vente in ventes_detail)
    
    # Derniers recouvrements
    recouvrements = Recouvrement.objects.filter(agent=agent).order_by('-date_recouvrement')[:5]
    
    # Ventes récentes (30 derniers jours)
    date_limite = timezone.now() - timedelta(days=30)
    ventes_recentes = ventes.filter(date_vente__gte=date_limite)
    
    context = {
        'agent': agent,
        'ventes': ventes[:10],  # 10 dernières ventes
        'ventes_total_count': ventes.count(),
        'ventes_gros': ventes_gros,
        'ventes_detail': ventes_detail,
        'total_ventes_gros': total_ventes_gros,
        'total_ventes_detail': total_ventes_detail,
        'total_ventes': total_ventes,
        'total_recouvre': total_recouvre,
        'argent_en_possession': argent_en_possession,
        'recouvrements': recouvrements,
        'ventes_recentes_count': ventes_recentes.count(),
    }
    
    return render(request, 'core/agents/detail_agent.html', context)

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
            password='temp123',  
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

#=========
#FOURNISSEUR
#========

@login_required
def liste_fournisseurs(request):
    fournisseurs = Fournisseur.objects.all()
    return render(request, 'core/fournisseur/liste_fournisseurs.html', {'fournisseurs': fournisseurs})

@login_required
def creer_fournisseur(request):
    if request.method == 'POST':
        form = FournisseurForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Fournisseur ajouté avec succès.")
            return redirect('liste_fournisseurs')
    else:
        form = FournisseurForm()
    return render(request, 'core/fournisseur/creer_fournisseur.html', {'form': form})

@login_required
def modifier_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    if request.method == 'POST':
        form = FournisseurForm(request.POST, instance=fournisseur)
        if form.is_valid():
            form.save()
            messages.success(request, "Fournisseur modifié avec succès.")
            return redirect('liste_fournisseurs')
    else:
        form = FournisseurForm(instance=fournisseur)
    return render(request, 'core/fournisseur/modifier_fournisseur.html', {'form': form})

@login_required
def supprimer_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    fournisseur.delete()
    messages.success(request, "Fournisseur supprimé avec succès.")
    return redirect('liste_fournisseurs')


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
                
                # Créer un mouvement de stock
                MouvementStock.objects.create(
                    produit=lot.produit,
                    lot=lot,
                    type_mouvement='RECEPTION',
                    quantite=lot.quantite_initiale,
                    date_mouvement=lot.date_reception
                )
                
                messages.success(request, f"✅ Lot {lot.reference_lot} réceptionné avec succès!")
                if lot.facture:
                    messages.info(request, "📎 Facture uploadée avec succès")
                return redirect('liste_lots')
                
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de l'enregistrement: {str(e)}")
        else:
            messages.error(request, "❌ Veuillez corriger les erreurs ci-dessous.")
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
    
    # Calcul des statistiques
    stats = lots.aggregate(
        total_lots=models.Count('id'),  # AJOUT IMPORTANT
        total_stock=models.Sum('quantite_restante'),
        lots_epuises=models.Count('id', filter=models.Q(quantite_restante=0)),
        total_valeur=models.Sum(
            models.F('quantite_restante') * models.F('prix_achat_unitaire')
        )
    )
    
    context = {
        'lots': lots,
        'total_lots': stats['total_lots'] or 0,  # CORRECTION ICI
        'total_stock': stats['total_stock'] or 0,
        'total_valeur': stats['total_valeur'] or 0,
        'lots_epuises': stats['lots_epuises'] or 0,
    }
    
    return render(request, 'core/entrepot/liste_lots.html', context)

# views.py
@login_required
def mon_stock(request):
    """Vue permettant à l'agent de consulter son stock personnel"""
    try:
        agent = request.user.agent
    except Agent.DoesNotExist:
        return redirect('access_denied')
    
    # Vérifier que l'utilisateur est un agent terrain
    if agent.type_agent not in ['terrain', 'entrepot']:
        return redirect('access_denied')
    
    # Calcul du stock actuel de l'agent
    stock_agent = calculer_stock_agent(agent)
    
    # Distributions reçues (30 derniers jours)
    distributions_recentes = DistributionAgent.objects.filter(
        agent_terrain=agent,
        est_supprime=False,
        date_distribution__gte=timezone.now() - timedelta(days=30)
    ).select_related('superviseur').prefetch_related('detaildistribution_set__lot__produit').order_by('-date_distribution')
    
    # Ventes récentes (7 derniers jours)
    ventes_recentes = Vente.objects.filter(
        agent=agent,
        date_vente__gte=timezone.now() - timedelta(days=7)
    ).select_related('client', 'detail_distribution__lot__produit').order_by('-date_vente')[:10]
    
    # Alertes stock faible
    alertes_stock_faible = []
    for produit_data in stock_agent:
        if produit_data['quantite_restante'] <= produit_data.get('seuil_alerte', 5):
            alertes_stock_faible.append(produit_data)
    
    context = {
        'agent': agent,
        'stock_agent': stock_agent,
        'distributions_recentes': distributions_recentes,
        'ventes_recentes': ventes_recentes,
        'alertes_stock_faible': alertes_stock_faible,
        'total_valeur_stock': sum(p['valeur_totale'] for p in stock_agent),
        'total_quantite': sum(p['quantite_restante'] for p in stock_agent),
    }
    
    return render(request, 'core/entrepot/mon_stock.html', context)

def calculer_stock_agent(agent):
    """
    Calcule le stock actuel d'un agent en fonction des distributions et ventes
    """
    # Récupérer toutes les distributions non supprimées pour cet agent
    distributions = DistributionAgent.objects.filter(
        agent_terrain=agent,
        est_supprime=False
    ).prefetch_related('detaildistribution_set__lot__produit')
    
    # Récupérer toutes les ventes de cet agent
    ventes = Vente.objects.filter(agent=agent).select_related('detail_distribution__lot__produit')
    
    # Calculer le stock par produit
    stock_par_produit = {}
    
    # Ajouter les quantités distribuées
    for distribution in distributions:
        for detail in distribution.detaildistribution_set.filter(est_supprime=False):
            produit = detail.lot.produit
            produit_id = produit.id
            
            if produit_id not in stock_par_produit:
                stock_par_produit[produit_id] = {
                    'produit': produit,
                    'quantite_distribuee': 0,
                    'quantite_vendue': 0,
                    'quantite_restante': 0,
                    'prix_gros': detail.prix_gros,
                    'prix_detail': detail.prix_detail,
                    'valeur_totale': 0,
                    'seuil_alerte': 5  # Seuil par défaut
                }
            
            stock_par_produit[produit_id]['quantite_distribuee'] += detail.quantite
    
    # Soustraire les quantités vendues
    for vente in ventes:
        produit = vente.detail_distribution.lot.produit
        produit_id = produit.id
        
        if produit_id in stock_par_produit:
            stock_par_produit[produit_id]['quantite_vendue'] += vente.quantite
    
    # Calculer les quantités restantes et valeurs
    for produit_id, data in stock_par_produit.items():
        data['quantite_restante'] = data['quantite_distribuee'] - data['quantite_vendue']
        
        # Calculer la valeur du stock (au prix de détail par défaut)
        if data['prix_detail'] and data['quantite_restante'] > 0:
            data['valeur_totale'] = data['quantite_restante'] * data['prix_detail']
        else:
            data['valeur_totale'] = 0
    
    # Convertir en liste et trier par quantité restante (décroissant)
    stock_list = list(stock_par_produit.values())
    stock_list.sort(key=lambda x: x['quantite_restante'], reverse=True)
    
    return stock_list

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
                with transaction.atomic():
                    distribution = form.save()
                
                # Message personnalisé selon le type de distribution
                if distribution.type_distribution == 'AUTO':
                    messages.success(request, f"✅ Auto-distribution #{distribution.id} créée avec succès! Vous pouvez maintenant vendre ces produits.")
                else:
                    messages.success(request, f"✅ Distribution #{distribution.id} vers {distribution.agent_terrain} créée avec succès!")
                
                return redirect('liste_distributions')
                
            except forms.ValidationError as e:
                messages.error(request, f"❌ {e}")
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de la distribution: {str(e)}")
        else:
            messages.error(request, "❌ Veuillez corriger les erreurs ci-dessous.")
    else:
        form = DistributionForm(current_user=request.user)
    
    return render(request, 'core/distribution/distribuer.html', {
        'form': form,
        'title': 'Nouvelle Distribution'
    })

@login_required
def modifier_distribution(request, distribution_id):
    """Modifier une distribution existante"""
    distribution = get_object_or_404(
        DistributionAgent.objects.select_related('superviseur', 'agent_terrain'),
        id=distribution_id,
        est_supprime=False
    )
    
    # Vérifier que l'utilisateur peut modifier cette distribution
    if not request.user.is_superuser and distribution.superviseur.user != request.user:
        messages.error(request, "Vous n'avez pas la permission de modifier cette distribution.")
        return redirect('liste_distributions')
    
    if request.method == 'POST':
        form = DistributionModificationForm(request.POST, instance=distribution, current_user=request.user)
        if form.is_valid():
            try:
                distribution_modifiee = form.save()
                
                # Mettre à jour les totaux
                distribution_modifiee._mettre_a_jour_totaux(user=request.user)
                
                # Journaliser la modification
                JournalModificationDistribution.objects.create(
                    distribution=distribution_modifiee,
                    utilisateur=request.user,
                    type_action='MODIFICATION',
                    details=f"Raison: {form.cleaned_data['raison_modification']}",
                    anciennes_valeurs={
                        'date_distribution': str(distribution.date_distribution),
                    },
                    nouvelles_valeurs={
                        'date_distribution': str(distribution_modifiee.date_distribution),
                    }
                )
                
                messages.success(request, f"✅ Distribution #{distribution.id} modifiée avec succès!")
                return redirect('detail_distribution', distribution_id=distribution.id)
                
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de la modification: {str(e)}")
    else:
        form = DistributionModificationForm(instance=distribution, current_user=request.user)
    
    context = {
        'form': form,
        'distribution': distribution,
        'title': f'Modifier Distribution #{distribution.id}'
    }
    
    return render(request, 'core/distribution/modifier_distribution.html', context)

@login_required
def supprimer_distribution(request, distribution_id):
    """Soft delete d'une distribution"""
    distribution = get_object_or_404(
        DistributionAgent.objects.select_related('superviseur', 'agent_terrain'),
        id=distribution_id,
        est_supprime=False
    )
    
    # Vérifier les permissions
    if not request.user.is_superuser and distribution.superviseur.user != request.user:
        messages.error(request, "Vous n'avez pas la permission de supprimer cette distribution.")
        return redirect('liste_distributions')
    
    if request.method == 'POST':
        form = DistributionSuppressionForm(request.POST)
        if form.is_valid():
            try:
                # Soft delete
                distribution.soft_delete(
                    user=request.user,
                    raison=form.cleaned_data['raison_suppression']
                )
                
                # Journaliser la suppression
                JournalModificationDistribution.objects.create(
                    distribution=distribution,
                    utilisateur=request.user,
                    type_action='SUPPRESSION',
                    details=f"Raison: {form.cleaned_data['raison_suppression']}"
                )
                
                messages.success(request, f"✅ Distribution #{distribution.id} supprimée avec succès!")
                return redirect('liste_distributions')
                
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de la suppression: {str(e)}")
    else:
        form = DistributionSuppressionForm()
    
    context = {
        'form': form,
        'distribution': distribution,
        'title': f'Supprimer Distribution #{distribution.id}'
    }
    
    return render(request, 'core/distribution/supprimer_distribution.html', context)

@login_required
def restaurer_distribution(request, distribution_id):
    """Restaurer une distribution supprimée"""
    distribution = get_object_or_404(
        DistributionAgent.objects.select_related('superviseur', 'agent_terrain'),
        id=distribution_id,
        est_supprime=True
    )
    
    if request.method == 'POST':
        try:
            distribution.restaurer(user=request.user)
            
            # Journaliser la restauration
            JournalModificationDistribution.objects.create(
                distribution=distribution,
                utilisateur=request.user,
                type_action='RESTAURATION',
                details="Distribution restaurée"
            )
            
            messages.success(request, f"✅ Distribution #{distribution.id} restaurée avec succès!")
            return redirect('detail_distribution', distribution_id=distribution.id)
            
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la restauration: {str(e)}")
    
    context = {
        'distribution': distribution,
        'title': f'Restaurer Distribution #{distribution.id}'
    }
    
    return render(request, 'core/distribution/restaurer_distribution.html', context)


@login_required
def liste_distributions(request):
    """Liste toutes les distributions - Vue épurée"""
    # Filtres
    show_deleted = request.GET.get('show_deleted') == 'true'
    type_filter = request.GET.get('type')
    agent_filter = request.GET.get('agent')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    # Base queryset
    distributions = DistributionAgent.objects.select_related(
        'superviseur', 'agent_terrain'
    ).prefetch_related(
        'detaildistribution_set__lot__produit'
    ).order_by('-date_distribution')
    
    # Appliquer les filtres
    if not show_deleted:
        distributions = distributions.filter(est_supprime=False)
    if type_filter:
        distributions = distributions.filter(type_distribution=type_filter)
    if agent_filter:
        distributions = distributions.filter(agent_terrain_id=agent_filter)
    if date_debut:
        distributions = distributions.filter(date_distribution__gte=date_debut)
    if date_fin:
        distributions = distributions.filter(date_distribution__lte=date_fin)
    
    # Calcul des totaux globaux
    total_distributions = distributions.count()
    total_quantite = sum(dist.quantite_totale for dist in distributions)
    total_valeur_gros = sum(dist.valeur_gros_totale for dist in distributions)
    total_valeur_detail = sum(dist.valeur_detail_totale for dist in distributions)
    
    context = {
        'distributions': distributions,
        'total_distributions': total_distributions,
        'total_quantite': total_quantite,
        'total_valeur_gros': total_valeur_gros,
        'total_valeur_detail': total_valeur_detail,
        'agents_terrain': Agent.objects.filter(type_agent='terrain'),
        'filter_type': type_filter,
        'filter_agent': agent_filter,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'show_deleted': show_deleted,
    }
    
    return render(request, 'core/distribution/liste_distributions.html', context)



@login_required
def detail_distribution(request, distribution_id):
    """Détail d'une distribution spécifique - Données immuables"""
    distribution = get_object_or_404(
        DistributionAgent.objects.select_related('superviseur', 'agent_terrain')
        .prefetch_related('detaildistribution_set__lot__produit'), 
        id=distribution_id
    )
    
    # Récupérer les détails figés
    details = distribution.detaildistribution_set.all()
    
    # Données immuables
    produits_distribues = []
    for detail in details:
        produits_distribues.append({
            'produit': detail.lot.produit,
            'lot': detail.lot,
            'quantite': detail.quantite,
            'prix_gros': detail.prix_gros,
            'prix_detail': detail.prix_detail,
            'valeur_gros': (detail.prix_gros or 0) * detail.quantite,
            'valeur_detail': (detail.prix_detail or 0) * detail.quantite,
        })
    
    # Totaux immuables
    quantite_totale = sum(detail.quantite for detail in details)
    valeur_gros_totale = sum((detail.prix_gros or 0) * detail.quantite for detail in details)
    valeur_detail_totale = sum((detail.prix_detail or 0) * detail.quantite for detail in details)
    
    context = {
        'distribution': distribution,
        'produits_distribues': produits_distribues,
        'quantite_totale': quantite_totale,
        'valeur_gros_totale': valeur_gros_totale,
        'valeur_detail_totale': valeur_detail_totale,
    }
    
    return render(request, 'core/distribution/detail_distribution.html', context)

def get_stock_produit_a_date(request):
    """API pour récupérer le stock d'un produit à une date donnée (AJAX)"""
    try:
        produit_id = request.GET.get('produit_id')
        date_str = request.GET.get('date')
        
        if not produit_id or not date_str:
            return JsonResponse({'error': 'Paramètres manquants'}, status=400)
        
        produit = Produit.objects.get(id=produit_id)
        date_reference = timezone.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        
        # Créer une instance de formulaire pour utiliser ses méthodes
        form = DistributionForm(current_user=request.user)
        stock_disponible = form.get_stock_a_date(produit.nom, date_reference)
        
        # Récupérer les vrais lots avec leurs quantités restantes
        lots_disponibles = form.get_lots_disponibles_a_date(produit.nom, date_reference)
        lots_info = []
        
        for lot in lots_disponibles:
            lots_info.append({
                'lot_id': lot.id,
                'reference': lot.reference_lot or f"Lot#{lot.id}",
                'quantite_restante': getattr(lot, '_quantite_restante_calculee', lot.quantite_restante),
                'date_reception': lot.date_reception.strftime('%d/%m/%Y'),
                'prix_achat': float(lot.prix_achat_unitaire)
            })
        
        return JsonResponse({
            'stock': stock_disponible,
            'produit': produit.nom,
            'lots_disponibles': lots_info,
            'date_reference': date_reference.strftime('%d/%m/%Y %H:%M')
        })
        
    except Produit.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# API pour récupérer le stock actuel (conservée pour compatibilité)
def get_stock_produit(request, produit_id):
    """API pour récupérer le stock actuel d'un produit (AJAX)"""
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

@login_required
def stats_superviseurs(request):
    """Statistiques des distributions et ventes des superviseurs"""
    # Récupérer le superviseur connecté
    superviseur = get_object_or_404(Agent, user=request.user)
    
    # Distributions du superviseur
    distributions = DistributionAgent.objects.filter(superviseur=superviseur)
    
    # Auto-distributions
    auto_distributions = distributions.filter(type_distribution='AUTO')
    
    # Distributions aux agents terrain
    distributions_terrain = distributions.filter(type_distribution='TERRAIN')
    
    # Calcul des statistiques
    stats = {
        'total_distributions': distributions.count(),
        'auto_distributions_count': auto_distributions.count(),
        'terrain_distributions_count': distributions_terrain.count(),
        'total_produits_distribues': sum(
            sum(detail.quantite for detail in dist.detaildistribution_set.all())
            for dist in distributions
        ),
        'valeur_totale_gros': sum(
            sum((detail.prix_gros or 0) * detail.quantite for detail in dist.detaildistribution_set.all())
            for dist in distributions
        ),
        'valeur_totale_detail': sum(
            sum((detail.prix_detail or 0) * detail.quantite for detail in dist.detaildistribution_set.all())
            for dist in distributions
        ),
    }
    
    # Top produits distribués
    produits_distribues = {}
    for dist in distributions:
        for detail in dist.detaildistribution_set.all():
            produit_nom = detail.lot.produit.nom
            if produit_nom not in produits_distribues:
                produits_distribues[produit_nom] = 0
            produits_distribues[produit_nom] += detail.quantite
    
    top_produits = sorted(produits_distribues.items(), key=lambda x: x[1], reverse=True)[:5]
    
    context = {
        'superviseur': superviseur,
        'stats': stats,
        'auto_distributions': auto_distributions[:10],  # 10 dernières
        'distributions_terrain': distributions_terrain[:10],  # 10 dernières
        'top_produits': top_produits,
    }
    
    return render(request, 'core/distribution/stats_superviseurs.html', context)


@login_required
def mes_distributions(request):
    """Vue permettant à l'agent de voir toutes ses distributions"""
    try:
        agent = request.user.agent
    except Agent.DoesNotExist:
        return redirect('access_denied')
    
    distributions = DistributionAgent.objects.filter(
        agent_terrain=agent,
        est_supprime=False
    ).select_related('superviseur').prefetch_related('detaildistribution_set__lot__produit').order_by('-date_distribution')
    
    # Calcul des statistiques
    total_produits_distribues = sum(dist.quantite_totale for dist in distributions)
    total_valeur_distribuee = sum(dist.valeur_detail_totale for dist in distributions)
    
    # Superviseurs distincts
    superviseurs_distincts = distributions.values('superviseur').distinct().count()
    
    # Statistiques par superviseur
    stats_superviseurs = distributions.values(
        'superviseur__user__first_name', 
        'superviseur__user__last_name'
    ).annotate(
        total_distributions=Count('id'),
        total_quantite=Sum('quantite_totale')
    ).order_by('-total_distributions')
    
    # Évolution mensuelle (6 derniers mois)
    evolution_mensuelle = []
    for i in range(6):
        mois_date = timezone.now() - timedelta(days=30*i)
        debut_mois = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin_mois = (debut_mois + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        distributions_mois = distributions.filter(
            date_distribution__range=[debut_mois, fin_mois]
        )
        
        quantite_totale = sum(dist.quantite_totale for dist in distributions_mois)
        
        evolution_mensuelle.append({
            'mois': debut_mois.strftime('%b %Y'),
            'quantite_totale': quantite_totale,
            'nombre_distributions': distributions_mois.count()
        })
    
    evolution_mensuelle.reverse()
    
    # Ajouter des propriétés aux distributions pour le template
    for distribution in distributions:
        # Couleur du statut
        if distribution.est_supprime:
            distribution.couleur_statut = 'danger'
            distribution.statut_display = 'Supprimée'
        elif distribution.est_modifie:
            distribution.couleur_statut = 'warning'
            distribution.statut_display = 'Modifiée'
        else:
            distribution.couleur_statut = 'success'
            distribution.statut_display = 'Active'
    
    context = {
        'agent': agent,
        'distributions': distributions,
        'total_produits_distribues': total_produits_distribues,
        'total_valeur_distribuee': total_valeur_distribuee,
        'superviseurs_distincts': superviseurs_distincts,
        'stats_superviseurs': stats_superviseurs,
        'evolution_mensuelle': evolution_mensuelle,
    }
    
    return render(request, 'core/distribution/mes_distributions.html', context)

#=====
#VENTE
#=====

@login_required
def enregistrer_vente(request):
    """Enregistrer une vente avec gestion des dettes"""
    # Récupérer l'agent connecté (sans restriction de type)
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé pour cet utilisateur.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = VenteForm(request.POST, agent=agent)
        
        if form.is_valid():
            try:
                with transaction.atomic():  # Transaction pour garantir l'intégrité
                    vente = form.save()
                    
                    # Si c'est une vente à crédit, créer la dette
                    if vente.mode_paiement == 'credit':
                        # Rediriger vers le formulaire de création de dette
                        request.session['vente_pending_dette'] = vente.id
                        messages.success(request, 
                            f"Vente à crédit enregistrée ! {vente.quantite} {vente.produit_nom} "
                            f"vendu à {vente.client.nom}. Veuillez compléter les informations de la dette."
                        )
                        return redirect('creer_dette')
                    
                    else:  # Vente comptant
                        messages.success(request, 
                            f"Vente comptant enregistrée ! {vente.quantite} {vente.produit_nom} "
                            f"vendu à {vente.client.nom} pour {vente.total_vente} FCFA"
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
    """Lister les ventes de l'agent avec statistiques"""
    # Récupérer l'agent connecté
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    # Récupérer les ventes de l'agent
    ventes = Vente.objects.filter(
        agent=agent
    ).select_related(
        'client', 
        'detail_distribution__lot__produit'
    ).prefetch_related('dette').order_by('-date_vente')
    
    # Calculer les statistiques
    total_ventes = ventes.count()
    chiffre_affaires_total = sum(vente.total_vente for vente in ventes)
    
    # Statistiques par type
    ventes_gros = ventes.filter(type_vente='gros')
    ventes_detail = ventes.filter(type_vente='detail')
    ventes_comptant = ventes.filter(mode_paiement='comptant')
    ventes_credit = ventes.filter(mode_paiement='credit')
    
    # Calculer les bonus obtenus
    bonus_obtenus = 0
    dettes_avec_bonus = Dette.objects.filter(
        vente__agent=agent,
        bonus_accorde=True
    )
    for dette in dettes_avec_bonus:
        bonus_obtenus += dette.montant_bonus
    
    # Dettes en cours
    dettes_en_cours = Dette.objects.filter(
        vente__agent=agent,
        statut__in=['en_cours', 'partiellement_paye', 'en_retard']
    ).count()
    
    context = {
        'ventes': ventes,
        'total_ventes': total_ventes,
        'chiffre_affaires_total': chiffre_affaires_total,
        'ventes_gros_count': ventes_gros.count(),
        'ventes_detail_count': ventes_detail.count(),
        'ventes_comptant_count': ventes_comptant.count(),
        'ventes_credit_count': ventes_credit.count(),
        'bonus_obtenus': bonus_obtenus,
        'dettes_en_cours': dettes_en_cours,
        'agent': agent,
    }
    
    return render(request, 'core/ventes/liste_ventes.html', context)

@login_required
def detail_dette(request, dette_id):
    """Détail d'une dette"""
    # Récupérer l'agent connecté
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    try:
        dette = Dette.objects.select_related(
            'vente', 
            'vente__client', 
            'vente__detail_distribution__lot__produit'
        ).get(id=dette_id, vente__agent=agent)
    except Dette.DoesNotExist:
        messages.error(request, "Dette non trouvée.")
        return redirect('liste_dettes')
    
    paiements = dette.paiements.all().order_by('-date_paiement')
    
    context = {
        'dette': dette,
        'paiements': paiements,
    }
    
    return render(request, 'core/ventes/detail_dette.html', context)

@login_required
def detail_vente(request, vente_id):
    """Détail d'une vente"""
    # Récupérer l'agent connecté
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    try:
        vente = Vente.objects.select_related(
            'client', 
            'detail_distribution__lot__produit'
        ).get(id=vente_id, agent=agent)
    except Vente.DoesNotExist:
        messages.error(request, "Vente non trouvée.")
        return redirect('liste_ventes')
    
    # Vérifier si c'est un crédit et récupérer la dette associée
    dette = None
    if vente.mode_paiement == 'credit':
        try:
            dette = vente.dette
        except Dette.DoesNotExist:
            pass
    
    context = {
        'vente': vente,
        'dette': dette,
    }
    
    return render(request, 'core/ventes/detail_vente.html', context)

@login_required
def enregistrer_paiement_dette(request, dette_id):
    """Enregistrer un paiement pour une dette"""
    # Récupérer l'agent connecté
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    try:
        dette = Dette.objects.get(id=dette_id, vente__agent=agent)
    except Dette.DoesNotExist:
        messages.error(request, "Dette non trouvée.")
        return redirect('liste_dettes')
    
    if dette.montant_restant <= 0:
        messages.info(request, "Cette dette est déjà entièrement payée.")
        return redirect('detail_dette', dette_id=dette.id)
    
    if request.method == 'POST':
        form = PaiementDetteForm(request.POST, dette=dette)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    paiement = form.save()
                    
                    # Vérifier si un bonus a été généré
                    bonus_message = ""
                    if paiement.bonus_genere:
                        bonus_message = f" Bonus de {paiement.nombre_produits_bonus * 100} FCFA accordé !"
                    
                    messages.success(request, 
                        f"Paiement enregistré ! Montant: {paiement.montant} FCFA - "
                        f"Reste à payer: {dette.montant_restant} FCFA.{bonus_message}"
                    )
                    return redirect('detail_dette', dette_id=dette.id)
                    
            except Exception as e:
                messages.error(request, f"Erreur lors de l'enregistrement du paiement: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = PaiementDetteForm(dette=dette)
    
    return render(request, 'core/ventes/enregistrer_paiement.html', {
        'form': form,
        'dette': dette
    })

@login_required
def consulter_bonus(request):
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    bonus_agent, created = BonusAgent.objects.get_or_create(agent=agent)
    
    dettes_bonus = Dette.objects.filter(
        vente__agent=agent,
        bonus_accorde=True
    ).select_related('vente', 'vente__client')
    
    # Statistiques mensuelles
    mois_courant = timezone.now().month
    annee_courante = timezone.now().year
    
    produits_recouverts_mois = bonus_agent.get_produits_recouverts_par_mois(mois_courant, annee_courante)
    bonus_mois = produits_recouverts_mois * 100

    # ✅ Moyenne par dette
    moyenne_par_dette = 0
    if dettes_bonus.exists():
        moyenne_par_dette = bonus_agent.total_bonus / dettes_bonus.count()

    context = {
        'bonus_agent': bonus_agent,
        'dettes_bonus': dettes_bonus,
        'produits_recouverts_mois': produits_recouverts_mois,
        'bonus_mois': bonus_mois,
        'mois_courant': mois_courant,
        'annee_courante': annee_courante,
        'moyenne_par_dette': moyenne_par_dette,  # ✅ ajouté
    }
    
    return render(request, 'core/ventes/consulter_bonus.html', context)


@login_required
def liste_dettes(request):
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    dettes = Dette.objects.filter(
        vente__agent=agent
    ).select_related(
        'vente',
        'vente__client',
        'vente__detail_distribution__lot__produit'
    ).order_by('-date_creation')
    
    # Filtres
    statut = request.GET.get('statut')
    if statut:
        dettes = dettes.filter(statut=statut)
    
    # Compteurs
    total_dettes = dettes.count()
    dettes_en_cours = dettes.filter(statut="en_cours").count()
    dettes_partiel = dettes.filter(statut="partiellement_paye").count()
    dettes_retard = dettes.filter(statut="en_retard").count()
    dettes_payees = dettes.filter(statut="paye").count()

    # Total montant restant
    total_restant = dettes.exclude(statut="paye").aggregate(
        total=models.Sum("montant_restant")
    )["total"] or 0

    context = {
        'dettes': dettes,
        'statut_actuel': statut,
        'total_dettes': total_dettes,
        'dettes_en_cours': dettes_en_cours,
        'dettes_partiel': dettes_partiel,
        'dettes_retard': dettes_retard,
        'dettes_payees': dettes_payees,
        'total_restant': total_restant,
    }
    
    return render(request, 'core/ventes/liste_dettes.html', context)


@login_required
def get_info_distribution(request, detail_id):
    """API pour récupérer les infos d'un détail de distribution - VERSION DEBUG"""
    try:
        print(f"Recherche détail distribution ID: {detail_id}")
        
        # Vérifier si le détail existe
        if not DetailDistribution.objects.filter(id=detail_id).exists():
            return JsonResponse({'error': f'Détail distribution {detail_id} non trouvé'}, status=404)
        
        detail = DetailDistribution.objects.get(id=detail_id)
        
        data = {
            'produit': detail.lot.produit.nom,
            'quantite_disponible': detail.quantite,
            'prix_gros': float(detail.prix_gros) if detail.prix_gros else None,
            'prix_detail': float(detail.prix_detail) if detail.prix_detail else None,
            'reference_lot': detail.lot.reference_lot or f"Lot#{detail.lot.id}",
        }
        
        print(f"Données retournées: {data}")
        return JsonResponse(data)
        
    except Exception as e:
        print(f"Erreur API: {str(e)}")
        return JsonResponse({'error': f'Erreur: {str(e)}'}, status=500)


@login_required
def creer_dette(request):
    """Créer une dette après une vente à crédit"""
    # Récupérer l'agent connecté
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    # Récupérer la vente en attente de création de dette
    vente_id = request.session.get('vente_pending_dette')
    if not vente_id:
        messages.error(request, "Aucune vente à crédit en attente.")
        return redirect('enregistrer_vente')
    
    try:
        vente = Vente.objects.get(id=vente_id, agent=agent)
    except Vente.DoesNotExist:
        messages.error(request, "Vente non trouvée.")
        return redirect('enregistrer_vente')
    
    # Vérifier si la dette existe déjà
    if hasattr(vente, 'dette'):
        messages.info(request, "Une dette existe déjà pour cette vente.")
        return redirect('detail_vente', vente_id=vente.id)
    
    if request.method == 'POST':
        form = DetteForm(request.POST, vente=vente)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    dette = form.save()
                    
                    # Nettoyer la session
                    if 'vente_pending_dette' in request.session:
                        del request.session['vente_pending_dette']
                    
                    messages.success(request, 
                        f"Dette créée ! Montant: {dette.montant_total} FCFA - "
                        f"Échéance: {dette.date_echeance} - Localité: {dette.nom_localite}"
                    )
                    return redirect('detail_dette', dette_id=dette.id)
                    
            except Exception as e:
                messages.error(request, f"Erreur lors de la création de la dette: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = DetteForm(vente=vente)
    
    return render(request, 'core/ventes/creer_dette.html', {
        'form': form,
        'vente': vente
    })
#=====
#FACTURE
#=====

# Liste des factures
def liste_factures(request):
    factures = Facture.objects.all().order_by('-date_depot')
    return render(request, 'core/factures/liste_factures.html', {'factures': factures})

# views.py
@login_required
def detail_lot(request, lot_id):
    """Détail d'un lot avec upload de facture"""
    lot = get_object_or_404(
        LotEntrepot.objects.select_related('produit', 'fournisseur'),
        id=lot_id
    )
    
    # Gérer l'upload de facture
    facture_uploadee = False
    if request.method == 'POST' and 'facture' in request.FILES:
        form = UploadFactureForm(request.POST, request.FILES, instance=lot)
        if form.is_valid():
            try:
                lot_modifie = form.save(commit=False)
                lot_modifie.date_upload_facture = timezone.now()
                lot_modifie.save()
                
                messages.success(request, "✅ Facture uploadée avec succès!")
                facture_uploadee = True
                
                # Recharger l'objet pour avoir les données fraîches
                lot = LotEntrepot.objects.get(id=lot_id)
                
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de l'upload: {str(e)}")
        else:
            messages.error(request, "❌ Veuillez corriger les erreurs ci-dessous.")
    else:
        form = UploadFactureForm(instance=lot)
    
    context = {
        'lot': lot,
        'form': form,
        'facture_uploadee': facture_uploadee,
        'title': f'Lot {lot.reference_lot}'
    }
    return render(request, 'core/entrepot/detail_lot.html', context)


@login_required
def liste_factures_entrepot(request):
    """Liste des factures liées aux réceptions d'entrepôt"""
    lots_avec_facture = LotEntrepot.objects.exclude(facture='').order_by('-date_reception')
    
    context = {
        'lots_avec_facture': lots_avec_facture,
        'title': 'Factures Entrepôt'
    }
    return render(request, 'core/factures/liste_factures_entrepot.html', context)
# Créer une facture

def creer_facture(request):
    if request.method == 'POST':
        form = FactureForm(request.POST, request.FILES)
        if form.is_valid():
            facture = form.save(commit=False)
            try:
                # Récupérer l'agent de l'utilisateur connecté
                facture.agent = Agent.objects.get(user=request.user)
            except Agent.DoesNotExist:
                # Créer l'agent automatiquement si inexistant
                facture.agent = Agent.objects.create(user=request.user, type_agent='entrepot')
            
            facture.save()
            messages.success(request, "Facture créée avec succès.")
            return redirect('liste_factures')
    else:
        form = FactureForm()
    
    return render(request, 'core/factures/form_facture.html', {'form': form, 'title': 'Nouvelle Facture'})

# Modifier une facture
def modifier_facture(request, facture_id):
    facture = get_object_or_404(Facture, id=facture_id)
    if request.method == 'POST':
        form = FactureForm(request.POST, request.FILES, instance=facture)
        if form.is_valid():
            form.save()
            messages.success(request, "Facture mise à jour.")
            return redirect('liste_factures')
    else:
        form = FactureForm(instance=facture)
    return render(request, 'core/factures/form_facture.html', {'form': form, 'title': 'Modifier Facture'})

# Supprimer une facture
def supprimer_facture(request, facture_id):
    facture = get_object_or_404(Facture, id=facture_id)
    if request.method == 'POST':
        facture.delete()
        messages.success(request, "Facture supprimée.")
        return redirect('liste_factures')
    return render(request, 'core/factures/confirm_delete.html', {'facture': facture})
#=========
# #RECOUVREMENT
#=========
@login_required
def creer_recouvrement(request, agent_id):
    # Récupérer l'agent cible (peut être terrain OU superviseur)
    agent = get_object_or_404(Agent, id=agent_id)
    agent_connecte = request.user.agent
    
    # Vérifications de sécurité
    if agent_connecte.est_agent_terrain:
        messages.error(request, "Les agents terrain ne peuvent pas effectuer de recouvrements.")
        return redirect('tableau_de_bord')
    
    # Un superviseur peut recouvrir ses propres ventes OU celles des agents terrain
    if agent_connecte.est_superviseur:
        if not (agent.est_agent_terrain or agent.id == agent_connecte.id):
            messages.error(request, "Vous ne pouvez recouvrir que vos propres ventes ou celles de vos agents terrain.")
            return redirect('tableau_de_bord')
    
    # Un directeur peut recouvrir tout le monde
    if agent_connecte.est_direction:
        if not (agent.est_agent_terrain or agent.est_superviseur):
            messages.error(request, "Vous ne pouvez recouvrir que les agents terrain et superviseurs.")
            return redirect('tableau_de_bord')
    
    if request.method == 'POST':
        form = RecouvrementForm(request.POST, agent=agent)
        if form.is_valid():
            # Créer le recouvrement avec les données supplémentaires
            recouvrement = form.save(commit=False)
            recouvrement.agent = agent
            recouvrement.superviseur = agent_connecte
            recouvrement.save()
            
            # Message personnalisé selon le type d'agent
            if agent.est_agent_terrain:
                message = f"Recouvrement de {recouvrement.montant_recouvre} FCFA effectué auprès de {agent.full_name} avec succès!"
            else:  # Auto-recouvrement
                message = f"Auto-recouvrement de {recouvrement.montant_recouvre} FCFA effectué avec succès!"
            
            messages.success(request, message)
            
            # Redirection appropriée
            if agent.est_agent_terrain:
                return redirect('detail_agent', agent_id=agent.id)
            else:
                return redirect('liste_agents_recouvrement')
    else:
        form = RecouvrementForm(agent=agent)
    
    context = {
        'agent': agent,
        'form': form,
        'argent_en_possession': agent.argent_en_possession,
        'total_ventes': agent.total_ventes,
        'total_recouvre': agent.total_recouvre,
        'est_auto_recouvrement': agent.id == agent_connecte.id,
    }
    
    return render(request, 'core/recouvrement/creer_recouvrement.html', context)


@login_required
def historique_recouvrement(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    recouvrements = Recouvrement.objects.filter(agent=agent).order_by('-date_recouvrement')
    
    context = {
        'agent': agent,
        'recouvrements': recouvrements,
    }
    
    return render(request, 'core/recouvrement/historique.html', context)

@login_required
def detail_historique(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    
    # Récupérer TOUS les recouvrements
    recouvrements = Recouvrement.objects.filter(agent=agent).order_by('-date_recouvrement')
    
    # Statistiques détaillées
    total_recouvre = agent.total_recouvre
    nombre_recouvrements = recouvrements.count()
    
    # Premier et dernier recouvrement
    premier_recouvrement = recouvrements.last()
    dernier_recouvrement = recouvrements.first()
    
    context = {
        'agent': agent,
        'recouvrements': recouvrements,
        'total_recouvre': total_recouvre,
        'nombre_recouvrements': nombre_recouvrements,
        'premier_recouvrement': premier_recouvrement,
        'dernier_recouvrement': dernier_recouvrement,
    }
    
    return render(request, 'core/recouvrement/detail_historique.html', context)

@login_required
def liste_agents_recouvrement(request):
    agent_connecte = request.user.agent
    
    # Déterminer quels agents afficher selon le type
    if agent_connecte.est_direction:
        # Direction voit tous les agents terrain ET superviseurs
        agents = Agent.objects.filter(type_agent__in=['terrain', 'superviseur'])
    elif agent_connecte.est_superviseur:
        # Superviseur voit ses agents terrain + lui-même
        agents_terrain = Agent.objects.filter(type_agent='terrain')
        agents = list(agents_terrain) + [agent_connecte]
    else:
        # Agent terrain ne voit personne
        agents = []
    
    agents_data = []
    agent_ids_deja_vus = []  # Liste pour suivre les IDs déjà traités
    
    for agent in agents:
        # Éviter les doublons en utilisant les IDs
        if agent.id in agent_ids_deja_vus:
            continue
        agent_ids_deja_vus.append(agent.id)
            
        total_ventes = agent.total_ventes
        total_recouvre = agent.total_recouvre
        difference = total_ventes - total_recouvre
        
        # Déterminer la couleur en fonction de la différence
        if difference == 0:
            couleur = 'success'
            statut = 'Complètement recouvré'
        elif difference > 0:
            couleur = 'warning'
            statut = f'{difference} FCFA à recouvrir'
        else:
            couleur = 'danger'
            statut = 'Erreur de calcul'
        
        agents_data.append({
            'agent': agent,
            'total_ventes': total_ventes,
            'total_recouvre': total_recouvre,
            'difference': difference,
            'couleur': couleur,
            'statut': statut,
            'est_auto_recouvrement': agent.id == agent_connecte.id,
        })
    
    # Trier par différence décroissante
    agents_data.sort(key=lambda x: x['difference'], reverse=True)
    
    context = {
        'agents_data': agents_data,
        'total_general_ventes': sum(item['total_ventes'] for item in agents_data),
        'total_general_recouvre': sum(item['total_recouvre'] for item in agents_data),
        'total_general_difference': sum(item['difference'] for item in agents_data),
        'agent_connecte': agent_connecte,
    }
    
    return render(request, 'core/recouvrement/liste_agents.html', context)

#=====
#CLIENT
#=====
# views.py
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'core/clients/liste_clients.html'
    context_object_name = 'clients'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Client.objects.all().order_by('nom')
        
        # Filtrage par type de client
        type_client = self.request.GET.get('type_client')
        if type_client:
            queryset = queryset.filter(type_client=type_client)
            
        # Recherche par nom
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(nom__icontains=search)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_clients'] = Client.objects.count()
        context['types_client'] = Client.TYPE_CLIENT_CHOICES
        return context

class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = 'core/clients/detail_client.html'
    context_object_name = 'client'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Récupérer l'historique des ventes pour ce client
        context['ventes'] = Vente.objects.filter(
            client=self.object
        ).select_related(
            'agent__user', 
            'detail_distribution__lot__produit'
        ).order_by('-date_vente')[:50]  # 50 dernières ventes
        
        # Calculer les statistiques du client
        ventes_client = Vente.objects.filter(client=self.object)
        context['total_ventes'] = ventes_client.count()
        context['chiffre_affaires'] = sum(
            vente.quantite * vente.prix_vente_unitaire for vente in ventes_client
        )
        context['produits_achetes'] = ventes_client.values(
            'detail_distribution__lot__produit__nom'
        ).distinct().count()
        
        return context

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    template_name = 'core/clients/ajouter_client.html'
    fields = ['nom', 'contact', 'type_client']
    success_url = reverse_lazy('liste_clients')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['nom'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Nom du client'})
        form.fields['contact'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Téléphone ou email'})
        form.fields['type_client'].widget.attrs.update({'class': 'form-select'})
        return form
    
    def form_valid(self, form):
        messages.success(self.request, f"Client {form.cleaned_data['nom']} créé avec succès!")
        return super().form_valid(form)

class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    template_name = 'core/clients/modifier_client.html'
    fields = ['nom', 'contact', 'type_client']
    
    def get_success_url(self):
        return reverse_lazy('detail_client', kwargs={'pk': self.object.pk})
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['nom'].widget.attrs.update({'class': 'form-control'})
        form.fields['contact'].widget.attrs.update({'class': 'form-control'})
        form.fields['type_client'].widget.attrs.update({'class': 'form-select'})
        return form
    
    def form_valid(self, form):
        messages.success(self.request, f"Client {form.cleaned_data['nom']} modifié avec succès!")
        return super().form_valid(form)

class ClientDeleteView(LoginRequiredMixin, DeleteView):

    model = Client
    template_name = 'core/clients/supprimer_client.html'
    success_url = reverse_lazy('liste_clients')
    
    def delete(self, request, *args, **kwargs):
        client = self.get_object()
        messages.success(request, f"Client {client.nom} supprimé avec succès!")
        return super().delete(request, *args, **kwargs)

#=====
#   Superviseur
#=====

@login_required
def tableau_de_bord_superviseur(request):
    # Vérifier que l'utilisateur est un superviseur
    try:
        superviseur = Agent.objects.get(user=request.user, type_agent='entrepot')
    except Agent.DoesNotExist:
        return render(request, 'errors/403.html', status=403)
    
    # Période pour les statistiques (30 derniers jours)
    date_debut = timezone.now() - timedelta(days=30)
    
    # Vue Stock
    stock_total = LotEntrepot.objects.filter(quantite_restante__gt=0).aggregate(
        total_quantite=Sum('quantite_restante'),
        total_valeur=Sum(F('quantite_restante') * F('prix_achat_unitaire'))
    )
    
    produits_stock = LotEntrepot.objects.filter(
        quantite_restante__gt=0
    ).values(
        'produit__nom'
    ).annotate(
        quantite_totale=Sum('quantite_restante'),
        valeur_totale=Sum(F('quantite_restante') * F('prix_achat_unitaire'))
    ).order_by('-quantite_totale')
    
    # Vue Agents
    agents_terrain = Agent.objects.filter(type_agent='terrain')
    
    # Performances des agents (ventes des 30 derniers jours)
    performances_agents = []
    for agent in agents_terrain:
        ventes_agent = Vente.objects.filter(
            agent=agent,
            date_vente__gte=date_debut
        ).aggregate(
            total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
            nombre_ventes=Count('id'),
            clients_distincts=Count('client', distinct=True)
        )
        
        distributions_agent = DistributionAgent.objects.filter(
            agent_terrain=agent,
            date_distribution__gte=date_debut
        ).aggregate(
            total_produits=Sum('quantite_totale')
        )
        
        performances_agents.append({
            'agent': agent,
            'total_ventes': ventes_agent['total_ventes'] or 0,
            'nombre_ventes': ventes_agent['nombre_ventes'] or 0,
            'clients_distincts': ventes_agent['clients_distincts'] or 0,
            'produits_distribues': distributions_agent['total_produits'] or 0
        })
    
    # Vue Ventes globales
    ventes_30j = Vente.objects.filter(date_vente__gte=date_debut).aggregate(
        total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes=Count('id'),
        quantite_vendue=Sum('quantite')
    )
    
    ventes_par_type = Vente.objects.filter(
        date_vente__gte=date_debut
    ).values(
        'type_vente'
    ).annotate(
        total=Sum(F('quantite') * F('prix_vente_unitaire')),
        count=Count('id')
    )
    
    # Vue personnelle du superviseur (en tant qu'agent vendeur)
    ventes_superviseur = Vente.objects.filter(
        agent=superviseur,
        date_vente__gte=date_debut
    ).aggregate(
        total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes=Count('id'),
        quantite_vendue=Sum('quantite')
    )
    
    distributions_superviseur = DistributionAgent.objects.filter(
        Q(superviseur=superviseur) | Q(agent_terrain=superviseur),
        date_distribution__gte=date_debut
    ).count()
    
    # Alertes stock faible
    seuil_stock_faible = 10
    stocks_faibles = LotEntrepot.objects.filter(
        quantite_restante__lte=seuil_stock_faible,
        quantite_restante__gt=0
    )
    
    # Dettes en cours
    dettes_en_cours = Dette.objects.filter(statut__in=['en_cours', 'partiellement_paye']).count()
    
    context = {
        'superviseur': superviseur,
        
        # Données stock
        'stock_total': stock_total,
        'produits_stock': produits_stock,
        'stocks_faibles': stocks_faibles,
        'seuil_stock_faible': seuil_stock_faible,
        
        # Données agents
        'agents_terrain': agents_terrain,
        'performances_agents': performances_agents,
        
        # Données ventes globales
        'ventes_30j': ventes_30j,
        'ventes_par_type': ventes_par_type,
        'date_debut': date_debut,
        
        # Données personnelles superviseur
        'ventes_superviseur': ventes_superviseur,
        'distributions_superviseur': distributions_superviseur,
        
        # Alertes
        'dettes_en_cours': dettes_en_cours,
    }
    
    return render(request, 'core/dashboard/superviseur.html', context)

@login_required
def vue_detail_agent(request, agent_id):
    superviseur = get_object_or_404(Agent, user=request.user, type_agent='entrepot')
    agent = get_object_or_404(Agent, id=agent_id, type_agent='terrain')
    
    # Période pour les statistiques
    date_debut = timezone.now() - timedelta(days=30)
    
    # Distributions reçues
    distributions = DistributionAgent.objects.filter(
        agent_terrain=agent,
        date_distribution__gte=date_debut
    ).order_by('-date_distribution')
    
    # Ventes de l'agent
    ventes = Vente.objects.filter(
        agent=agent,
        date_vente__gte=date_debut
    ).select_related('client', 'detail_distribution__lot__produit').order_by('-date_vente')
    
    # Statistiques ventes
    stats_ventes = ventes.aggregate(
        total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes=Count('id'),
        quantite_vendue=Sum('quantite')
    )
    
    # Dettes de l'agent
    dettes = Dette.objects.filter(
        vente__agent=agent,
        statut__in=['en_cours', 'partiellement_paye']
    ).select_related('vente__client')
    
    context = {
        'superviseur': superviseur,
        'agent_cible': agent,
        'distributions': distributions,
        'ventes': ventes[:10],  # 10 dernières ventes
        'stats_ventes': stats_ventes,
        'dettes': dettes,
        'date_debut': date_debut,
    }
    
    return render(request, 'core/dashboard/detail_agent.html', context)




#=========
# #ADMIN
#=========
    


#=========
#DASHBOARD
#========

@login_required
def toutes_les_ventes(request):
    """Voir toutes les ventes (pour administration)"""
    ventes = Vente.objects.select_related(
        'agent', 'client', 'detail_distribution__lot__produit'
    ).order_by('-date_vente')
    
    # Filtres
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    agent_id = request.GET.get('agent')
    type_vente = request.GET.get('type')
    
    if date_debut:
        ventes = ventes.filter(date_vente__gte=date_debut)
    if date_fin:
        ventes = ventes.filter(date_vente__lte=date_fin)
    if agent_id:
        ventes = ventes.filter(agent_id=agent_id)
    if type_vente:
        ventes = ventes.filter(type_vente=type_vente)
    
    # Statistiques
    total_ca = sum(vente.total_vente for vente in ventes)
    clients_count = ventes.values('client').distinct().count()
    agents_count = ventes.values('agent').distinct().count()
    
    ventes_gros = ventes.filter(type_vente='gros').count()
    ventes_detail = ventes.filter(type_vente='detail').count()
    
    # Top agents par CA
    top_agents = ventes.values(
        'agent__user__first_name', 
        'agent__user__last_name'
    ).annotate(
        total_ca=Sum(F('quantite') * F('prix_vente_unitaire'))
    ).order_by('-total_ca')[:5]
    
    # Liste des agents pour le filtre
    agents_list = Agent.objects.filter(type_agent='terrain')
    
    context = {
        'ventes': ventes,
        'total_ca': total_ca,
        'clients_count': clients_count,
        'agents_count': agents_count,
        'ventes_gros': ventes_gros,
        'ventes_detail': ventes_detail,
        'top_agents': top_agents,
        'agents_list': agents_list,
        'toutes_ventes': True,
    }
    
    return render(request, 'core/analyses/liste_ventes_admin.html', context)

@login_required
def toutes_les_dettes(request):
    """Voir toutes les dettes (pour administration)"""
    dettes = Dette.objects.select_related(
        'vente', 'vente__agent', 'vente__client', 'vente__detail_distribution__lot__produit'
    ).order_by('-date_creation')
    
    # Filtres
    statut = request.GET.get('statut')
    agent_id = request.GET.get('agent')
    delai = request.GET.get('delai')
    
    if statut:
        dettes = dettes.filter(statut=statut)
    if agent_id:
        dettes = dettes.filter(vente__agent_id=agent_id)
    if delai:
        today = timezone.now().date()
        if delai == 'retard':
            dettes = dettes.filter(date_echeance__lt=today, statut__in=['en_cours', 'partiellement_paye'])
        elif delai == 'bonus':
            dettes = dettes.filter(eligible_bonus=True)
        else:
            days = int(delai)
            target_date = today + timedelta(days=days)
            dettes = dettes.filter(date_echeance__lte=target_date, statut__in=['en_cours', 'partiellement_paye'])
    
    # Statistiques
    total_montant_total = sum(dette.montant_total for dette in dettes)
    total_montant_restant = sum(dette.montant_restant for dette in dettes)
    
    dettes_en_cours = dettes.filter(statut='en_cours').count()
    dettes_partiellement_payees = dettes.filter(statut='partiellement_paye').count()
    dettes_payees = dettes.filter(statut='paye').count()
    dettes_en_retard = dettes.filter(statut='en_retard').count()
    
    # Taux de recouvrement
    taux_recouvrement = ((total_montant_total - total_montant_restant) / total_montant_total * 100) if total_montant_total > 0 else 0
    
    # Top 5 dettes les plus importantes
    top_dettes = dettes.filter(statut__in=['en_cours', 'partiellement_paye', 'en_retard']).order_by('-montant_restant')[:5]
    
    # Liste des agents pour le filtre
    agents_list = Agent.objects.filter(type_agent='terrain')
    
    context = {
        'dettes': dettes,
        'statut_actuel': statut,
        'total_montant_total': total_montant_total,
        'total_montant_restant': total_montant_restant,
        'dettes_en_cours': dettes_en_cours,
        'dettes_partiellement_payees': dettes_partiellement_payees,
        'dettes_payees': dettes_payees,
        'dettes_en_retard': dettes_en_retard,
        'taux_recouvrement': taux_recouvrement,
        'top_dettes': top_dettes,
        'agents_list': agents_list,
        'toutes_dettes': True,
    }
    
    return render(request, 'core/analyses/liste_dettes_admin.html', context)


@login_required
def tous_les_bonus(request):
    """Voir tous les bonus (pour administration)"""
    bonus_agents = BonusAgent.objects.select_related('agent').order_by('-total_bonus')
    
    context = {
        'bonus_agents': bonus_agents,
        'tous_bonus': True,
    }
    
    return render(request, 'core/analyses/tous_les_bonus_admin.html', context)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/analyses/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Périodes
        today = timezone.now()
        debut_mois = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_semaine = today - timedelta(days=today.weekday())
        
        # === CHIFFRE D'AFFAIRES ===
        ventes_mois = Vente.objects.filter(date_vente__gte=debut_mois)
        ventes_semaine = Vente.objects.filter(date_vente__gte=debut_semaine)
        
        # Calcul manuel du CA pour éviter les problèmes d'annotation
        ca_mois = 0
        for vente in ventes_mois:
            ca_mois += float(vente.quantite * vente.prix_vente_unitaire)
            
        ca_semaine = 0
        for vente in ventes_semaine:
            ca_semaine += float(vente.quantite * vente.prix_vente_unitaire)
            
        ca_total = 0
        for vente in Vente.objects.all():
            ca_total += float(vente.quantite * vente.prix_vente_unitaire)
        
        # === CLIENTS PAR TYPE ===
        # Méthode alternative sans multiplication dans l'annotation
        clients_par_type = []
        for type_client, label in Client.TYPE_CLIENT_CHOICES:
            clients = Client.objects.filter(type_client=type_client)
            ventes_clients = Vente.objects.filter(client__type_client=type_client)
            
            total_ca = 0
            for vente in ventes_clients:
                total_ca += float(vente.quantite * vente.prix_vente_unitaire)
                
            clients_par_type.append({
                'type_client': type_client,
                'label': label,
                'total': clients.count(),
                'total_ventes': ventes_clients.count(),
                'total_ca': total_ca
            })
        
        # Trier par CA décroissant
        clients_par_type.sort(key=lambda x: x['total_ca'], reverse=True)
        
        # === MOUVEMENT PRODUITS (DÉTAIL vs GROS) ===
        # Ventilation détail vs gros
        ventilation_type = []
        for type_vente, label in Vente.TYPE_VENTE_CHOICES:
            ventes_type = Vente.objects.filter(type_vente=type_vente)
            
            total_quantite = sum(vente.quantite for vente in ventes_type)
            total_ca = 0
            for vente in ventes_type:
                total_ca += float(vente.quantite * vente.prix_vente_unitaire)
                
            ventilation_type.append({
                'type_vente': type_vente,
                'label': label,
                'total_quantite': total_quantite,
                'total_ca': total_ca,
                'nombre_ventes': ventes_type.count()
            })
        
        # === PRODUITS VENDUS ===
        produits_vendus_data = {}
        for vente in Vente.objects.all():
            produit_nom = vente.detail_distribution.lot.produit.nom
            if produit_nom not in produits_vendus_data:
                produits_vendus_data[produit_nom] = {
                    'total_quantite': 0,
                    'total_ca': 0,
                    'ventes_count': 0
                }
            
            produits_vendus_data[produit_nom]['total_quantite'] += vente.quantite
            produits_vendus_data[produit_nom]['total_ca'] += float(vente.quantite * vente.prix_vente_unitaire)
            produits_vendus_data[produit_nom]['ventes_count'] += 1
        
        # Convertir en liste et trier
        produits_vendus = [
            {
                'nom': nom,
                'total_quantite': data['total_quantite'],
                'total_ca': data['total_ca'],
                'ventes_count': data['ventes_count']
            }
            for nom, data in produits_vendus_data.items()
        ]
        produits_vendus.sort(key=lambda x: x['total_ca'], reverse=True)
        produits_vendus = produits_vendus[:10]  # Top 10
        
        # === CLIENTS ACTIFS ===
        clients_actifs_mois = ventes_mois.values('client').distinct().count()
        clients_actifs_semaine = ventes_semaine.values('client').distinct().count()
        clients_total = Client.objects.count()
        
        # === PANIER MOYEN ===
        panier_moyen_mois = ca_mois / ventes_mois.count() if ventes_mois.count() > 0 else 0
        panier_moyen_semaine = ca_semaine / ventes_semaine.count() if ventes_semaine.count() > 0 else 0
        
        # === TAUX ROTATION STOCK ===
        distributions_mois = DetailDistribution.objects.filter(
            distribution__date_distribution__gte=debut_mois
        )
        quantite_distribuee = sum(dist.quantite for dist in distributions_mois)
        quantite_vendue = sum(vente.quantite for vente in ventes_mois)
        
        taux_rotation = (quantite_vendue / quantite_distribuee * 100) if quantite_distribuee > 0 else 0
        
        # === TOP CLIENTS RENTABLES ===
        clients_data = {}
        for vente in Vente.objects.all():
            client_nom = vente.client.nom
            client_type = vente.client.type_client
            
            if client_nom not in clients_data:
                clients_data[client_nom] = {
                    'type_client': client_type,
                    'total_achats': 0,
                    'nombre_commandes': 0,
                    'montants_commandes': []
                }
            
            montant_commande = float(vente.quantite * vente.prix_vente_unitaire)
            clients_data[client_nom]['total_achats'] += montant_commande
            clients_data[client_nom]['nombre_commandes'] += 1
            clients_data[client_nom]['montants_commandes'].append(montant_commande)
        
        # Calculer le panier moyen et créer la liste
        top_clients = []
        for client_nom, data in clients_data.items():
            panier_moyen = data['total_achats'] / data['nombre_commandes'] if data['nombre_commandes'] > 0 else 0
            top_clients.append({
                'nom': client_nom,
                'type_client': data['type_client'],
                'total_achats': data['total_achats'],
                'nombre_commandes': data['nombre_commandes'],
                'panier_moyen': panier_moyen
            })
        
        top_clients.sort(key=lambda x: x['total_achats'], reverse=True)
        top_clients = top_clients[:10]  # Top 10
        
        # === ÉVOLUTION MENSUELLE ===
        evolution_data = []
        for i in range(6):  # 6 derniers mois
            mois_date = today - timedelta(days=30*i)
            debut_mois_ref = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fin_mois_ref = (debut_mois_ref + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            ventes_mois_ref = Vente.objects.filter(date_vente__range=[debut_mois_ref, fin_mois_ref])
            ca_mois_ref = 0
            for vente in ventes_mois_ref:
                ca_mois_ref += float(vente.quantite * vente.prix_vente_unitaire)
            
            evolution_data.append({
                'mois': debut_mois_ref.strftime('%b %Y'),
                'ca': ca_mois_ref
            })
        
        evolution_data.reverse()
        
        context.update({
            # Chiffre d'affaires
            'ca_mois': ca_mois,
            'ca_semaine': ca_semaine,
            'ca_total': ca_total,
            'ventes_mois': ventes_mois.count(),
            'ventes_semaine': ventes_semaine.count(),
            
            # Clients
            'clients_par_type': clients_par_type,
            'clients_actifs_mois': clients_actifs_mois,
            'clients_actifs_semaine': clients_actifs_semaine,
            'clients_total': clients_total,
            'top_clients': top_clients,
            
            # Produits
            'ventilation_type': ventilation_type,
            'produits_vendus': produits_vendus,
            'quantite_vendue_mois': quantite_vendue,
            
            # Performance
            'panier_moyen_mois': panier_moyen_mois,
            'panier_moyen_semaine': panier_moyen_semaine,
            'taux_rotation': taux_rotation,
            
            # Évolution
            'evolution_data': evolution_data,
        })
        
        return context
    
class PerformanceAgentsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/analyses/stat_agents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Périodes
        today = timezone.now()
        debut_mois = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_semaine = today - timedelta(days=today.weekday())
        
        # === CONFIGURATION DES OBJECTIFS ===
        OBJECTIF_JACKPOT = 500  # Jackpot à 500 produits
        PALIER_1 = 200  # Premier palier
        PALIER_2 = 300  # Deuxième palier
        
        def get_couleur_objectif(nombre_produits):
            """Retourne la couleur en fonction du nombre de produits vendus"""
            if nombre_produits >= OBJECTIF_JACKPOT:
                return "success"  # Vert - Jackpot atteint
            elif nombre_produits >= PALIER_2:
                return "warning"  # Orange - Palier 2
            elif nombre_produits >= PALIER_1:
                return "info"    # Bleu - Palier 1
            else:
                return "danger"  # Rouge - En dessous des objectifs
        
        def get_statut_objectif(nombre_produits):
            """Retourne le statut textuel de l'objectif"""
            if nombre_produits >= OBJECTIF_JACKPOT:
                return "Jackpot Atteint! 🎉"
            elif nombre_produits >= PALIER_2:
                return f"Palier 2 (> {PALIER_2})"
            elif nombre_produits >= PALIER_1:
                return f"Palier 1 (> {PALIER_1})"
            else:
                return f"Objectif en cours (< {PALIER_1})"
        
        # === PERFORMANCE GLOBALE DES AGENTS ===
        agents_performance = []
        agents = Agent.objects.select_related('user')
        
        for agent in agents:
            # Ventes de l'agent
            ventes_agent = Vente.objects.filter(agent=agent)
            ventes_mois = ventes_agent.filter(date_vente__gte=debut_mois)
            ventes_semaine = ventes_agent.filter(date_vente__gte=debut_semaine)
            
            # Calculs manuels pour éviter les problèmes d'annotation
            ca_total = 0
            ca_mois = 0
            ca_semaine = 0
            quantite_total = 0
            quantite_mois = 0
            quantite_semaine = 0
            
            for vente in ventes_agent:
                montant = float(vente.quantite * vente.prix_vente_unitaire)
                ca_total += montant
                quantite_total += vente.quantite
            
            for vente in ventes_mois:
                montant = float(vente.quantite * vente.prix_vente_unitaire)
                ca_mois += montant
                quantite_mois += vente.quantite
                
            for vente in ventes_semaine:
                montant = float(vente.quantite * vente.prix_vente_unitaire)
                ca_semaine += montant
                quantite_semaine += vente.quantite
            
            # Clients servis
            clients_servis = ventes_agent.values('client').distinct().count()
            clients_mois = ventes_mois.values('client').distinct().count()
            
            # Efficacité commerciale (CA moyen par vente)
            efficacite = ca_total / ventes_agent.count() if ventes_agent.count() > 0 else 0
            
            # === OBJECTIFS BASÉS SUR LE NOMBRE DE PRODUITS ===
            objectif_jackpot = OBJECTIF_JACKPOT
            produits_mois = quantite_mois
            
            # Calcul du pourcentage vers le jackpot
            pourcentage_jackpot = min((produits_mois / objectif_jackpot) * 100, 100) if objectif_jackpot > 0 else 0
            
            # Couleur et statut de l'objectif
            couleur_objectif = get_couleur_objectif(produits_mois)
            statut_objectif = get_statut_objectif(produits_mois)
            
            # Indicateur de progression vers le prochain palier
            if produits_mois < PALIER_1:
                prochain_palier = PALIER_1
                produits_restants = PALIER_1 - produits_mois
            elif produits_mois < PALIER_2:
                prochain_palier = PALIER_2
                produits_restants = PALIER_2 - produits_mois
            elif produits_mois < OBJECTIF_JACKPOT:
                prochain_palier = OBJECTIF_JACKPOT
                produits_restants = OBJECTIF_JACKPOT - produits_mois
            else:
                prochain_palier = None
                produits_restants = 0
            
            agents_performance.append({
                'agent': agent,
                'ca_total': ca_total,
                'ca_mois': ca_mois,
                'ca_semaine': ca_semaine,
                'ventes_total': ventes_agent.count(),
                'ventes_mois': ventes_mois.count(),
                'ventes_semaine': ventes_semaine.count(),
                'clients_servis': clients_servis,
                'clients_mois': clients_mois,
                'quantite_total': quantite_total,
                'quantite_mois': quantite_mois,
                'quantite_semaine': quantite_semaine,
                'efficacite': efficacite,
                'objectif_jackpot': objectif_jackpot,
                'produits_mois': produits_mois,
                'pourcentage_jackpot': pourcentage_jackpot,
                'couleur_objectif': couleur_objectif,
                'statut_objectif': statut_objectif,
                'prochain_palier': prochain_palier,
                'produits_restants': produits_restants,
                'palier_1': PALIER_1,
                'palier_2': PALIER_2,
                'panier_moyen': ca_total / ventes_agent.count() if ventes_agent.count() > 0 else 0,
            })
        
        # Trier par nombre de produits du mois (performance objectif)
        agents_performance.sort(key=lambda x: x['produits_mois'], reverse=True)
        
        # === STATISTIQUES GLOBALES ===
        total_agents = len(agents_performance)
        ca_mois_total = sum(agent['ca_mois'] for agent in agents_performance)
        ca_total_global = sum(agent['ca_total'] for agent in agents_performance)
        produits_mois_total = sum(agent['quantite_mois'] for agent in agents_performance)
        moyenne_efficacite = sum(agent['efficacite'] for agent in agents_performance) / total_agents if total_agents > 0 else 0
        
        # Statistiques des objectifs
        agents_jackpot = sum(1 for agent in agents_performance if agent['produits_mois'] >= OBJECTIF_JACKPOT)
        agents_palier_2 = sum(1 for agent in agents_performance if agent['produits_mois'] >= PALIER_2)
        agents_palier_1 = sum(1 for agent in agents_performance if agent['produits_mois'] >= PALIER_1)
        
        # === TOP PERFORMERS ===
        top_performers_produits = sorted(agents_performance, key=lambda x: x['produits_mois'], reverse=True)[:3]
        top_performers_mois = sorted(agents_performance, key=lambda x: x['ca_mois'], reverse=True)[:3]
        top_performers_clients = sorted(agents_performance, key=lambda x: x['clients_servis'], reverse=True)[:3]
        top_performers_efficacite = sorted(agents_performance, key=lambda x: x['efficacite'], reverse=True)[:3]
        
        # === ÉVOLUTION MENSUELLE PAR AGENT ===
        evolution_agents = {}
        evolution_months = []
        
        # Récupérer les mois une fois pour toutes
        for i in range(6):  # 6 derniers mois
            mois_date = today - timedelta(days=30*i)
            debut_mois_ref = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            evolution_months.append({
                'mois': debut_mois_ref.strftime('%b %Y'),
                'date': debut_mois_ref
            })
        
        evolution_months.reverse()
        
        for agent_perf in agents_performance[:5]:  # Top 5 agents seulement
            agent = agent_perf['agent']
            evolution_data = []
            
            for month_data in evolution_months:
                debut_mois_ref = month_data['date']
                fin_mois_ref = (debut_mois_ref + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                ventes_mois_ref = Vente.objects.filter(
                    agent=agent,
                    date_vente__range=[debut_mois_ref, fin_mois_ref]
                )
                
                ca_mois_ref = 0
                produits_mois_ref = 0
                for vente in ventes_mois_ref:
                    ca_mois_ref += float(vente.quantite * vente.prix_vente_unitaire)
                    produits_mois_ref += vente.quantite
                
                evolution_data.append({
                    'mois': month_data['mois'],
                    'ca': ca_mois_ref,
                    'produits': produits_mois_ref
                })
            
            evolution_agents[agent.user.get_full_name()] = evolution_data
        
        context.update({
            'agents_performance': agents_performance,
            'total_agents': total_agents,
            'ca_mois_total': ca_mois_total,
            'ca_total_global': ca_total_global,
            'produits_mois_total': produits_mois_total,
            'moyenne_efficacite': moyenne_efficacite,
            'agents_jackpot': agents_jackpot,
            'agents_palier_2': agents_palier_2,
            'agents_palier_1': agents_palier_1,
            'top_performers_produits': top_performers_produits,
            'top_performers_mois': top_performers_mois,
            'top_performers_clients': top_performers_clients,
            'top_performers_efficacite': top_performers_efficacite,
            'evolution_agents': evolution_agents,
            'evolution_months': evolution_months,
            'OBJECTIF_JACKPOT': OBJECTIF_JACKPOT,
            'PALIER_1': PALIER_1,
            'PALIER_2': PALIER_2,
        })
        
        return context

class AnalyseProduitsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/analyses/analyse_produits.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now()
        debut_mois = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # === PERFORMANCE PAR PRODUIT ===
        produits_data = {}
        
        for vente in Vente.objects.select_related('detail_distribution__lot__produit'):
            produit = vente.detail_distribution.lot.produit
            produit_nom = produit.nom
            
            if produit_nom not in produits_data:
                produits_data[produit_nom] = {
                    'produit': produit,
                    'total_quantite': 0,
                    'total_ca': 0,
                    'ventes_count': 0,
                    'clients_count': set(),
                    'agents_count': set(),
                    'ventes_mois': 0,
                    'ca_mois': 0,
                    'quantite_mois': 0,
                }
            
            data = produits_data[produit_nom]
            data['total_quantite'] += vente.quantite
            data['total_ca'] += float(vente.quantite * vente.prix_vente_unitaire)
            data['ventes_count'] += 1
            data['clients_count'].add(vente.client.id)
            data['agents_count'].add(vente.agent.id)
            
            # Ventes du mois
            if vente.date_vente >= debut_mois:
                data['ventes_mois'] += 1
                data['ca_mois'] += float(vente.quantite * vente.prix_vente_unitaire)
                data['quantite_mois'] += vente.quantite
        
        # Conversion en liste
        produits_performance = []
        for nom, data in produits_data.items():
            produits_performance.append({
                'produit': data['produit'],
                'total_quantite': data['total_quantite'],
                'total_ca': data['total_ca'],
                'ventes_count': data['ventes_count'],
                'clients_count': len(data['clients_count']),
                'agents_count': len(data['agents_count']),
                'ventes_mois': data['ventes_mois'],
                'ca_mois': data['ca_mois'],
                'quantite_mois': data['quantite_mois'],
                'panier_moyen': data['total_ca'] / data['ventes_count'] if data['ventes_count'] > 0 else 0,
                'taux_rotation_mois': (data['quantite_mois'] / data['total_quantite'] * 100) if data['total_quantite'] > 0 else 0,
            })
        
        # Tris multiples
        produits_par_ca = sorted(produits_performance, key=lambda x: x['total_ca'], reverse=True)
        produits_par_quantite = sorted(produits_performance, key=lambda x: x['total_quantite'], reverse=True)
        produits_par_rotation = sorted(produits_performance, key=lambda x: x['taux_rotation_mois'], reverse=True)
        
        # === STOCK VS VENTES ===
        stock_ventes_data = []
        for lot in LotEntrepot.objects.filter(quantite_restante__gt=0).select_related('produit'):
            produit_nom = lot.produit.nom
            ventes_produit = next((p for p in produits_performance if p['produit'].nom == produit_nom), None)
            
            if ventes_produit:
                taux_ecoulement = (ventes_produit['quantite_mois'] / lot.quantite_restante * 100) if lot.quantite_restante > 0 else 100
                jours_stock = (lot.quantite_restante / ventes_produit['quantite_mois'] * 30) if ventes_produit['quantite_mois'] > 0 else 999
            else:
                taux_ecoulement = 0
                jours_stock = 999
            
            stock_ventes_data.append({
                'produit': lot.produit,
                'stock_restant': lot.quantite_restante,
                'ventes_mois': ventes_produit['quantite_mois'] if ventes_produit else 0,
                'taux_ecoulement': taux_ecoulement,
                'jours_stock': jours_stock,
                'statut_stock': 'FAIBLE' if jours_stock < 15 else 'NORMAL' if jours_stock < 60 else 'EXCÉDENTAIRE'
            })
        
        # === SAISONNALITÉ PAR PRODUIT ===
        saisonnalite_data = {}
        for produit in Produit.objects.all():
            ventes_produit = Vente.objects.filter(
                detail_distribution__lot__produit=produit
            )
            
            # Ventilation par mois
            ventilation_mois = []
            for i in range(12):  # 12 derniers mois
                mois_date = today - timedelta(days=30*i)
                debut_mois_ref = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                fin_mois_ref = (debut_mois_ref + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                ventes_mois = ventes_produit.filter(date_vente__range=[debut_mois_ref, fin_mois_ref])
                quantite_mois = sum(vente.quantite for vente in ventes_mois)
                
                ventilation_mois.append({
                    'mois': debut_mois_ref.strftime('%b %Y'),
                    'quantite': quantite_mois,
                    'date': debut_mois_ref
                })
            
            ventilation_mois.reverse()
            saisonnalite_data[produit.nom] = ventilation_mois
        
        context.update({
            'produits_par_ca': produits_par_ca[:20],
            'produits_par_quantite': produits_par_quantite[:20],
            'produits_par_rotation': produits_par_rotation[:20],
            'stock_ventes_data': sorted(stock_ventes_data, key=lambda x: x['jours_stock']),
            'saisonnalite_data': saisonnalite_data,
            'total_produits': len(produits_performance),
            'ca_total_produits': sum(p['total_ca'] for p in produits_performance),
            'quantite_total_vendue': sum(p['total_quantite'] for p in produits_performance),
        })
        
        return context

class AnalyseClientsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/analyses/analyse_clients.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now()
        debut_mois = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_annee = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # === SEGMENTATION CLIENT DÉTAILLÉE ===
        clients_data = {}
        
        for client in Client.objects.select_related():
            ventes_client = Vente.objects.filter(client=client)
            ventes_mois = ventes_client.filter(date_vente__gte=debut_mois)
            ventes_annee = ventes_client.filter(date_vente__gte=debut_annee)
            
            # Calculs détaillés
            total_achats = 0
            total_achats_mois = 0
            total_achats_annee = 0
            nombre_commandes = ventes_client.count()
            nombre_produits = 0
            produits_achetes = set()
            
            for vente in ventes_client:
                montant = float(vente.quantite * vente.prix_vente_unitaire)
                total_achats += montant
                nombre_produits += vente.quantite
                produits_achetes.add(vente.detail_distribution.lot.produit.nom)
                
                if vente.date_vente >= debut_mois:
                    total_achats_mois += montant
                if vente.date_vente >= debut_annee:
                    total_achats_annee += montant
            
            # Fréquence d'achat
            if nombre_commandes > 0:
                anciennete_jours = (today - client.date_creation).days
                frequence_achat = anciennete_jours / nombre_commandes if anciennete_jours > 0 else 0
            else:
                frequence_achat = 0
            
            # Dernière commande
            derniere_commande = ventes_client.order_by('-date_vente').first()
            jours_inactivite = (today - derniere_commande.date_vente).days if derniere_commande else (today - client.date_creation).days
            
            clients_data[client.id] = {
                'client': client,
                'total_achats': total_achats,
                'total_achats_mois': total_achats_mois,
                'total_achats_annee': total_achats_annee,
                'nombre_commandes': nombre_commandes,
                'nombre_produits': nombre_produits,
                'produits_achetes': len(produits_achetes),
                'panier_moyen': total_achats / nombre_commandes if nombre_commandes > 0 else 0,
                'frequence_achat': frequence_achat,
                'anciennete_jours': (today - client.date_creation).days,
                'derniere_commande': derniere_commande,
                'jours_inactivite': jours_inactivite,
                'ventes_mois': ventes_mois.count(),
                'ventes_annee': ventes_annee.count(),
            }
        
        # Conversion en liste
        clients_analyse = list(clients_data.values())
        
        # === SEGMENTATION RFM (Récence, Fréquence, Montant) ===
        for client_data in clients_analyse:
            # Score Récence (1-5, 5 étant le meilleur)
            if client_data['jours_inactivite'] <= 7:
                client_data['score_recence'] = 5
            elif client_data['jours_inactivite'] <= 30:
                client_data['score_recence'] = 4
            elif client_data['jours_inactivite'] <= 90:
                client_data['score_recence'] = 3
            elif client_data['jours_inactivite'] <= 180:
                client_data['score_recence'] = 2
            else:
                client_data['score_recence'] = 1
            
            # Score Fréquence (1-5)
            if client_data['frequence_achat'] <= 7:
                client_data['score_frequence'] = 5
            elif client_data['frequence_achat'] <= 30:
                client_data['score_frequence'] = 4
            elif client_data['frequence_achat'] <= 90:
                client_data['score_frequence'] = 3
            elif client_data['frequence_achat'] <= 180:
                client_data['score_frequence'] = 2
            else:
                client_data['score_frequence'] = 1
            
            # Score Montant (1-5)
            if client_data['panier_moyen'] >= 100000:
                client_data['score_montant'] = 5
            elif client_data['panier_moyen'] >= 50000:
                client_data['score_montant'] = 4
            elif client_data['panier_moyen'] >= 20000:
                client_data['score_montant'] = 3
            elif client_data['panier_moyen'] >= 10000:
                client_data['score_montant'] = 2
            else:
                client_data['score_montant'] = 1
            
            # Score RFM total et segment
            client_data['score_rfm'] = client_data['score_recence'] + client_data['score_frequence'] + client_data['score_montant']
            
            # Segmentation
            if client_data['score_rfm'] >= 13:
                client_data['segment'] = 'VIP'
                client_data['couleur_segment'] = 'success'
            elif client_data['score_rfm'] >= 10:
                client_data['segment'] = 'Fidèle'
                client_data['couleur_segment'] = 'info'
            elif client_data['score_rfm'] >= 7:
                client_data['segment'] = 'Régulier'
                client_data['couleur_segment'] = 'warning'
            else:
                client_data['segment'] = 'Occasionnel'
                client_data['couleur_segment'] = 'secondary'
        
        # === CALCUL DES SEGMENTS ===
        clients_vip = [c for c in clients_analyse if c['segment'] == 'VIP']
        clients_fideles = [c for c in clients_analyse if c['segment'] == 'Fidèle']
        clients_reguliers = [c for c in clients_analyse if c['segment'] == 'Régulier']
        clients_occasionnels = [c for c in clients_analyse if c['segment'] == 'Occasionnel']
        
        # === ANALYSE PAR TYPE DE CLIENT ===
        analyse_par_type = {}
        for type_client, label in Client.TYPE_CLIENT_CHOICES:
            clients_type = [c for c in clients_analyse if c['client'].type_client == type_client]
            
            if clients_type:
                analyse_par_type[type_client] = {
                    'label': label,
                    'nombre_clients': len(clients_type),
                    'ca_total': sum(c['total_achats'] for c in clients_type),
                    'ca_moyen': sum(c['total_achats'] for c in clients_type) / len(clients_type),
                    'panier_moyen': sum(c['panier_moyen'] for c in clients_type) / len(clients_type),
                    'frequence_moyenne': sum(c['frequence_achat'] for c in clients_type) / len(clients_type),
                    'clients_vip': len([c for c in clients_type if c['segment'] == 'VIP']),
                }
        
        # === TOP CLIENTS PAR CRITÈRES ===
        top_clients_ca = sorted(clients_analyse, key=lambda x: x['total_achats'], reverse=True)[:10]
        top_clients_frequence = sorted(clients_analyse, key=lambda x: x['nombre_commandes'], reverse=True)[:10]
        top_clients_panier = sorted(clients_analyse, key=lambda x: x['panier_moyen'], reverse=True)[:10]
        clients_inactifs = [c for c in clients_analyse if c['jours_inactivite'] > 90]
        
        # === ÉVOLUTION DU PORTEFEUILLE CLIENTS ===
        evolution_clients = []
        for i in range(12):  # 12 derniers mois
            mois_date = today - timedelta(days=30*i)
            debut_mois_ref = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fin_mois_ref = (debut_mois_ref + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            # Nouveaux clients du mois
            nouveaux_clients = Client.objects.filter(
                date_creation__range=[debut_mois_ref, fin_mois_ref]
            ).count()
            
            # Clients actifs du mois (au moins une commande)
            clients_actifs = Vente.objects.filter(
                date_vente__range=[debut_mois_ref, fin_mois_ref]
            ).values('client').distinct().count()
            
            evolution_clients.append({
                'mois': debut_mois_ref.strftime('%b %Y'),
                'nouveaux_clients': nouveaux_clients,
                'clients_actifs': clients_actifs,
            })
        
        evolution_clients.reverse()
        
        context.update({
            'clients_analyse': clients_analyse,
            'analyse_par_type': analyse_par_type,
            'top_clients_ca': top_clients_ca,
            'top_clients_frequence': top_clients_frequence,
            'top_clients_panier': top_clients_panier,
            'clients_vip': clients_vip,
            'clients_fideles': clients_fideles,
            'clients_reguliers': clients_reguliers,
            'clients_occasionnels': clients_occasionnels,
            'clients_inactifs': clients_inactifs,
            'evolution_clients': evolution_clients,
            'total_clients': len(clients_analyse),
            'ca_total_clients': sum(c['total_achats'] for c in clients_analyse),
            'taux_vip': (len(clients_vip) / len(clients_analyse) * 100) if clients_analyse else 0,
        })
        
        return context

class AnalyseAgentsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/analyses/analyse_agents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now()
        debut_mois = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_trimestre = today - timedelta(days=90)
        
        # === ANALYSE DÉTAILLÉE DES AGENTS ===
        agents_analyse = []
        
        for agent in Agent.objects.select_related('user').filter(type_agent='terrain'):
            ventes_agent = Vente.objects.filter(agent=agent)
            ventes_mois = ventes_agent.filter(date_vente__gte=debut_mois)
            ventes_trimestre = ventes_agent.filter(date_vente__gte=debut_trimestre)
            
            # Calculs détaillés
            ca_total = 0
            ca_mois = 0
            ca_trimestre = 0
            quantite_total = 0
            clients_servis = set()
            produits_vendus = set()
            montants_ventes = []
            
            for vente in ventes_agent:
                montant = float(vente.quantite * vente.prix_vente_unitaire)
                ca_total += montant
                quantite_total += vente.quantite
                clients_servis.add(vente.client.id)
                produits_vendus.add(vente.detail_distribution.lot.produit.nom)
                montants_ventes.append(montant)
                
                if vente.date_vente >= debut_mois:
                    ca_mois += montant
                if vente.date_vente >= debut_trimestre:
                    ca_trimestre += montant
            
            # Indicateurs de performance
            nombre_ventes = ventes_agent.count()
            panier_moyen = ca_total / nombre_ventes if nombre_ventes > 0 else 0
            efficacite = ca_total / len(clients_servis) if clients_servis else 0
            
            # Taux de conversion (basé sur les distributions)
            distributions_agent = DistributionAgent.objects.filter(agent_terrain=agent)
            quantite_distribuee = sum(
                detail.quantite for dist in distributions_agent 
                for detail in dist.detaildistribution_set.all()
            )
            taux_conversion = (quantite_total / quantite_distribuee * 100) if quantite_distribuee > 0 else 0
            
            # Performance temporelle
            if nombre_ventes > 0:
                anciennete_jours = (today - ventes_agent.earliest('date_vente').date_vente).days
                ventes_par_jour = nombre_ventes / anciennete_jours if anciennete_jours > 0 else 0
            else:
                ventes_par_jour = 0
            
            # Dettes et recouvrement
            dettes_agent = Dette.objects.filter(vente__agent=agent)
            dettes_actives = dettes_agent.exclude(statut='paye')
            taux_recouvrement = (
                (dettes_agent.filter(statut='paye').count() / dettes_agent.count() * 100) 
                if dettes_agent.count() > 0 else 100
            )
            
            # Score de performance composite
            score_performance = (
                (ca_mois / max(ca_mois, 1)) * 40 +  # Poids CA: 40%
                (taux_conversion / 100) * 30 +       # Poids conversion: 30%
                (taux_recouvrement / 100) * 20 +     # Poids recouvrement: 20%
                (len(clients_servis) / max(len(clients_servis), 1)) * 10  # Poids clientèle: 10%
            )
            
            agents_analyse.append({
                'agent': agent,
                'ca_total': ca_total,
                'ca_mois': ca_mois,
                'ca_trimestre': ca_trimestre,
                'quantite_total': quantite_total,
                'nombre_ventes': nombre_ventes,
                'clients_servis': len(clients_servis),
                'produits_vendus': len(produits_vendus),
                'panier_moyen': panier_moyen,
                'efficacite': efficacite,
                'taux_conversion': taux_conversion,
                'ventes_par_jour': ventes_par_jour,
                'dettes_actives': dettes_actives.count(),
                'taux_recouvrement': taux_recouvrement,
                'score_performance': score_performance,
                'grade_performance': 'A' if score_performance >= 80 else 'B' if score_performance >= 60 else 'C',
                'couleur_grade': 'success' if score_performance >= 80 else 'warning' if score_performance >= 60 else 'danger',
            })
        
        # === COMPARAISON ET CLASSEMENT ===
        agents_par_performance = sorted(agents_analyse, key=lambda x: x['score_performance'], reverse=True)
        agents_par_ca = sorted(agents_analyse, key=lambda x: x['ca_mois'], reverse=True)
        agents_par_conversion = sorted(agents_analyse, key=lambda x: x['taux_conversion'], reverse=True)
        agents_par_clients = sorted(agents_analyse, key=lambda x: x['clients_servis'], reverse=True)
        
        # === ANALYSE DES TENDANCES ===
        tendances_agents = {}
        for agent_data in agents_analyse[:5]:  # Top 5 agents
            agent = agent_data['agent']
            evolution_data = []
            
            for i in range(6):  # 6 derniers mois
                mois_date = today - timedelta(days=30*i)
                debut_mois_ref = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                fin_mois_ref = (debut_mois_ref + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                ventes_mois_ref = Vente.objects.filter(
                    agent=agent,
                    date_vente__range=[debut_mois_ref, fin_mois_ref]
                )
                
                ca_mois_ref = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_mois_ref)
                clients_mois_ref = ventes_mois_ref.values('client').distinct().count()
                
                evolution_data.append({
                    'mois': debut_mois_ref.strftime('%b %Y'),
                    'ca': ca_mois_ref,
                    'clients': clients_mois_ref,
                    'ventes': ventes_mois_ref.count()
                })
            
            evolution_data.reverse()
            tendances_agents[agent.user.get_full_name()] = evolution_data
        
        context.update({
            'agents_analyse': agents_analyse,
            'agents_par_performance': agents_par_performance,
            'agents_par_ca': agents_par_ca,
            'agents_par_conversion': agents_par_conversion,
            'agents_par_clients': agents_par_clients,
            'tendances_agents': tendances_agents,
            'moyenne_performance': sum(a['score_performance'] for a in agents_analyse) / len(agents_analyse) if agents_analyse else 0,
            'top_performer': agents_par_performance[0] if agents_par_performance else None,
            'meilleur_conversion': agents_par_conversion[0] if agents_par_conversion else None,
        })
        
        return context