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
from .models import (
    Agent, Client, Vente, Produit, Facture,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,
    Recouvrement,VersementBancaire,VersementBancaire,RecuVersement
)

# Project forms
from .forms import (
    VenteForm, DistributionForm, ReceptionLotForm, FactureForm,
    DetteForm, PaiementDetteForm, DistributionSuppressionForm,
    DistributionModificationForm,UploadFactureForm,RecouvrementForm,
    FournisseurForm,VersementForm,AgentCreationForm, 
    AgentModificationForm

)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


from django.contrib.auth import authenticate, login
from django.contrib import messages
from core.forms import TelephoneOrUsernameLoginForm
from core.models import Agent

def custom_login(request):
    if request.method == "POST":
        form = TelephoneOrUsernameLoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            user = authenticate(request, username=username, password=password)

            if user:
                login(request, user)

                # 🔹 CAS 1 : Utilisateur staff / Direction interne
                if user.is_staff or user.is_superuser:
                    # S'ils ont un dashboard direction
                    return redirect("dashboard")

                # 🔹 CAS 2 : Utilisateur lié à un Agent
                agent = Agent.objects.filter(user=user).first()

                if agent:
                    # Cas direction
                    if agent.type_agent == "direction":
                        return redirect("dashboard")

                    # Cas superviseur (entrepôt)
                    elif agent.type_agent == "entrepot":
                        return redirect("tableau_de_bord_superviseur")

                    # Cas terrain
                    elif agent.type_agent == "terrain":
                        return redirect("dashboard_agent")

                    # Cas stagiaire ou autre
                    return redirect("dashboard_agent")

                # 🔹 CAS 3 : Aucun agent + pas staff = compte mal configuré
                messages.warning(request, "Aucun profil agent associé à ce compte.")
                return redirect("login")

            else:
                messages.error(request, "Numéro de téléphone ou mot de passe incorrect.")

    else:
        form = TelephoneOrUsernameLoginForm()

    return render(request, "registration/login.html", {"form": form})


def logout_user(request):
    logout(request)  
    return redirect('login') 

def custom_403(request, exception=None):
    return render(request, 'core/errors/403.html', status=403)
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
    agents = Agent.objects.filter(type_agent__in=['entrepot', 'terrain','stagiaire'])
    
    # Tri par type et statut
    agents_superviseurs = agents.filter(type_agent='entrepot').order_by('user__first_name')
    agents_terrain = agents.filter(type_agent='terrain').order_by('user__first_name')
    stagiaires = agents.filter(type_agent='stagiaire')
    stagiaires_actifs = stagiaires.filter(date_expiration__gte=timezone.now()).order_by('date_expiration')
    stagiaires_expires = stagiaires.filter(date_expiration__lt=timezone.now()).order_by('-date_expiration')
    
    context = {
        'agents': agents,
        'agents_superviseurs': agents_superviseurs,
        'agents_terrain': agents_terrain,
        'stagiaires': stagiaires,
        'stagiaires_actifs': stagiaires_actifs,
        'stagiaires_expires': stagiaires_expires,
    }
    
    return render(request, 'core/agents/liste_agents.html', context)

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
    """Uniquement pour les superviseurs - créer agent terrain, stagiaire OU superviseur"""
    # Vérifier que c'est un superviseur
    try:
        superviseur = request.user.agent
        if not superviseur.est_superviseur:
            messages.error(request, "❌ Seuls les superviseurs peuvent créer des agents.")
            return redirect('dashboard')
    except:
        messages.error(request, "❌ Accès non autorisé.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AgentCreationForm(request.POST)
        if form.is_valid():
            try:
                agent = form.save()
                
                # ✅ Messages personnalisés selon le type
                if agent.est_stagiaire:
                    messages.success(request, f"✅ Stagiaire {agent.full_name} créé ! Test de 15 jours. ")
                elif agent.est_superviseur:
                    messages.success(request, f"✅ Superviseur {agent.full_name} créé ! ")
                else:
                    messages.success(request, f"✅ Agent terrain {agent.full_name} créé ! ")
                
                return redirect('liste_agents')
                
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de la création: {str(e)}")
    else:
        form = AgentCreationForm()
    
    return render(request, 'core/agents/creer_agent.html', {'form': form})

@login_required
def modifier_agent(request, agent_id):
    """Modifier un agent - promotion simple"""
    agent = get_object_or_404(Agent, id=agent_id)
    
    if request.method == 'POST':
        form = AgentModificationForm(request.POST, instance=agent)
        if form.is_valid():
            ancien_type = agent.type_agent
            agent_modifie = form.save()
            
            # Message simple si promotion de stagiaire
            if ancien_type == 'stagiaire' and not agent_modifie.est_stagiaire:
                messages.success(request, f"✅ {agent_modifie.full_name} promu {agent_modifie.get_type_agent_display()} !")
            else:
                messages.success(request, f"✅ Agent modifié avec succès !")
                
            return redirect('liste_agents')
    else:
        form = AgentModificationForm(instance=agent)
    
    return render(request, 'core/agents/modifier_agent.html', {
        'form': form, 
        'agent': agent
    })

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

from django.db.models import Sum, Count, Avg, F, Max, Min


@login_required
def liste_fournisseurs(request):
    fournisseurs = Fournisseur.objects.annotate(
        # KPI financiers
        total_achats=Sum(F('lotentrepot__quantite_initiale') * F('lotentrepot__prix_achat_unitaire')),
        total_achats_restants=Sum(F('lotentrepot__quantite_restante') * F('lotentrepot__prix_achat_unitaire')),
        
        # KPI quantitatifs
        nb_lots_total=Count('lotentrepot'),
        nb_lots_actifs=Count('lotentrepot', filter=Q(lotentrepot__quantite_restante__gt=0)),
        
        # KPI temporels
        dernier_lot=Max('lotentrepot__date_reception'),
        premier_lot=Min('lotentrepot__date_reception'),
    ).order_by('-total_achats')  # Tri par CA décroissant
    
    return render(request, 'core/fournisseur/liste_fournisseurs.html', {
        'fournisseurs': fournisseurs
    })

@login_required
def detail_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    
    # Lots du fournisseur
    lots = LotEntrepot.objects.filter(fournisseur=fournisseur).select_related('produit').order_by('-date_reception')
    
    # KPI détaillés
    kpi = {
        'total_achats': lots.aggregate(
            total=Sum(F('quantite_initiale') * F('prix_achat_unitaire'))
        )['total'] or 0,
        
        'stock_actuel_valeur': lots.filter(quantite_restante__gt=0).aggregate(
            total=Sum(F('quantite_restante') * F('prix_achat_unitaire'))
        )['total'] or 0,
        
        'nb_lots_total': lots.count(),
        'nb_lots_actifs': lots.filter(quantite_restante__gt=0).count(),
        'nb_produits_différents': lots.values('produit').distinct().count(),
        
        'moyenne_commande': lots.aggregate(
            moyenne=Avg(F('quantite_initiale') * F('prix_achat_unitaire'))
        )['moyenne'] or 0,
        
        'derniere_activite': lots.aggregate(
            dernier=Max('date_reception')
        )['dernier'],
        
        'jours_sans_activite': (timezone.now() - lots.aggregate(
            dernier=Max('date_reception')
        )['dernier']).days if lots.exists() else None,
    }
    
    # Produits les plus achetés
    produits_populaires = lots.values('produit__nom').annotate(
        total_achete=Sum(F('quantite_initiale') * F('prix_achat_unitaire')),
        nb_lots=Count('id')
    ).order_by('-total_achete')[:5]
    
    # Évolution des achats (3 derniers mois)
    date_limite = timezone.now() - timedelta(days=90)
    recent_lots = lots.filter(date_reception__gte=date_limite)
    
    context = {
        'fournisseur': fournisseur,
        'lots': lots,
        'kpi': kpi,
        'produits_populaires': produits_populaires,
        'recent_lots': recent_lots,
    }
    return render(request, 'core/fournisseur/detail_fournisseur.html', context)

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
    
    # Calcul des statistiques avec les nouvelles métriques
    stats = lots.aggregate(
        total_lots=models.Count('id'),
        total_stock=models.Sum('quantite_restante'),
        lots_epuises=models.Count('id', filter=models.Q(quantite_restante=0)),
        total_valeur_initiale=models.Sum('valeur_stock_initiale'),
        total_valeur_actuelle=models.Sum(
            models.F('quantite_restante') * models.F('prix_achat_unitaire')
        )
    )
    
    context = {
        'lots': lots,
        'total_lots': stats['total_lots'] or 0,
        'total_stock': stats['total_stock'] or 0,
        'total_valeur_initiale': stats['total_valeur_initiale'] or 0,
        'total_valeur_actuelle': stats['total_valeur_actuelle'] or 0,
        'lots_epuises': stats['lots_epuises'] or 0,
    }
    
    return render(request, 'core/entrepot/liste_lots.html', context)

# core/views.py

from django.shortcuts import render, get_object_or_404, redirect
from core.models import LotEntrepot
from core.forms import PerteForm


@login_required
def detail_lot(request, lot_id):
    lot = get_object_or_404(
        LotEntrepot.objects.select_related('produit', 'fournisseur'),
        id=lot_id
    )

    facture_uploadee = False

    # --- FORMULAIRE PERTE (POST sans fichier) ---
    if request.method == 'POST' and 'quantite_perdue' in request.POST:
        perte_form = PerteForm(request.POST)
        if perte_form.is_valid():
            perte = perte_form.save(commit=False)

            if perte.quantite_perdue > lot.quantite_restante:
                messages.error(request, "❌ La quantité perdue dépasse la quantité restante.")
            else:
                perte.lot = lot
                perte.save()
                messages.success(request, "🛑 Perte enregistrée avec succès.")
                return redirect("detail_lot", lot_id=lot.id)
        else:
            messages.error(request, "❌ Formulaire de perte invalide.")
    else:
        perte_form = PerteForm()

    # --- FORMULAIRE FACTURE (POST avec fichier) ---
    if request.method == 'POST' and 'facture' in request.FILES:
        facture_form = UploadFactureForm(request.POST, request.FILES, instance=lot)
        if facture_form.is_valid():
            try:
                lot_modifie = facture_form.save(commit=False)
                lot_modifie.date_upload_facture = timezone.now()
                lot_modifie.save()

                messages.success(request, "📄 Facture uploadée avec succès!")
                facture_uploadee = True

                lot = LotEntrepot.objects.get(id=lot_id)

            except Exception as e:
                messages.error(request, f"❌ Erreur : {str(e)}")
        else:
            messages.error(request, "❌ Veuillez corriger les erreurs de la facture.")
    else:
        facture_form = UploadFactureForm(instance=lot)

    pertes = lot.pertes.all().order_by('-date_perte')

    return render(request, 'core/entrepot/detail_lot.html', {
        'lot': lot,
        'form': facture_form,
        'perte_form': perte_form,
        'pertes': pertes,
        'facture_uploadee': facture_uploadee,
        'title': f'Lot {lot.reference_lot}'
    })


# views.py
@login_required
def mon_stock(request):
    """Vue permettant à l'agent de consulter son stock personnel"""
    try:
        agent = request.user.agent
    except Agent.DoesNotExist:
        return redirect('login')
    
    # Vérifier que l'utilisateur est un agent terrain
    if agent.type_agent not in ['terrain', 'entrepot','stagiaire']:
        return redirect('login')
    
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
    
    # Calcul des totaux CORRIGÉS
    total_quantite = sum(p['quantite_restante'] for p in stock_agent)
    total_valeur_stock = sum(p['valeur_totale'] for p in stock_agent if p['quantite_restante'] > 0)
    total_produits = len([p for p in stock_agent if p['quantite_restante'] != 0])
    
    context = {
        'agent': agent,
        'stock_agent': stock_agent,
        'distributions_recentes': distributions_recentes,
        'ventes_recentes': ventes_recentes,
        'alertes_stock_faible': alertes_stock_faible,
        'total_valeur_stock': total_valeur_stock,
        'total_quantite': total_quantite,
        'total_produits': total_produits,
        'total_alertes': len(alertes_stock_faible),
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
    
    # Calculer les quantités restantes et valeurs CORRIGÉ
    for produit_id, data in stock_par_produit.items():
        data['quantite_restante'] = data['quantite_distribuee'] - data['quantite_vendue']
        
        # CORRECTION : Calculer la valeur du stock SEULEMENT si le stock est positif
        if data['quantite_restante'] > 0 and data['prix_detail']:
            data['valeur_totale'] = data['quantite_restante'] * data['prix_detail']
        else:
            data['valeur_totale'] = 0
        
        # CORRECTION : Ajuster l'affichage pour les stocks négatifs
        if data['quantite_restante'] < 0:
            # Pour l'affichage, on peut garder la valeur négative mais la valeur monétaire doit être 0
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
                    messages.success(request, f"✅ Auto-distribution #{distribution.id} créée avec succès !")
                elif distribution.type_distribution == 'STAGIAIRE':
                    messages.success(request, f"✅ Distribution #{distribution.id} envoyée à un stagiaire ({distribution.agent_terrain}) avec succès !")
                else:
                    messages.success(request, f"✅ Distribution #{distribution.id} vers {distribution.agent_terrain} créée avec succès !")
                
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
    """Détail d'une distribution spécifique"""
    distribution = get_object_or_404(
        DistributionAgent.objects.select_related('superviseur', 'agent_terrain')
        .prefetch_related('detaildistribution_set__lot__produit'), 
        id=distribution_id
    )
    
    # Récupérer les détails
    produits_distribues = distribution.detaildistribution_set.select_related('lot__produit')
    
    context = {
        'distribution': distribution,
        'produits_distribues': produits_distribues,
    }
    
    return render(request, 'core/distribution/detail_distribution.html', context)



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
    """Enregistrer une vente avec gestion des dettes et stagiaires"""
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
                    
                    # Récupérer le nom du client en utilisant la propriété nom_client
                    nom_client_affichage = vente.nom_client
                    
                    # ✅ NOUVEAU : Message personnalisé selon le type de vente
                    if vente.stagiaire:
                        message_success = (
                            f"✅ Vente stagiaire enregistrée ! {vente.quantite} {vente.produit_nom} "
                            f"vendu par {vente.stagiaire.full_name} à {nom_client_affichage} "
                            f"pour {vente.total_vente} FCFA"
                        )
                    else:
                        message_success = (
                            f"✅ Vente enregistrée ! {vente.quantite} {vente.produit_nom} "
                            f"vendu à {nom_client_affichage} pour {vente.total_vente} FCFA"
                        )
                    
                    # Si c'est une vente à crédit, créer la dette
                    if vente.mode_paiement == 'credit':
                        # Rediriger vers le formulaire de création de dette
                        request.session['vente_pending_dette'] = vente.id
                        messages.success(request, f"{message_success} - Veuillez compléter les informations de la dette.")
                        return redirect('creer_dette')
                    
                    else:  # Vente comptant
                        messages.success(request, message_success)
                        return redirect('liste_ventes')
                        
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de l'enregistrement: {str(e)}")
        else:
            messages.error(request, "❌ Veuillez corriger les erreurs ci-dessous.")
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
        return redirect('liste_ventes')
    
    # Récupérer les ventes de l'agent
    ventes = Vente.objects.filter(
        agent=agent
    ).select_related(
        'client', 
        'detail_distribution__lot__produit',
        'stagiaire'
    ).prefetch_related('dette').order_by('-date_vente')
    
    # Calculer les statistiques
    total_ventes = ventes.count()
    
    # Calculer le chiffre d'affaires avec F() expressions
    stats_ventes = ventes.aggregate(
        chiffre_affaires_total=Sum(F('quantite') * F('prix_vente_unitaire')),
        quantite_totale=Sum('quantite')
    )
    
    # ✅ CORRECTION : Gérer les valeurs None
    chiffre_affaires_total = stats_ventes['chiffre_affaires_total'] or Decimal('0.00')
    
    # Statistiques par type
    ventes_gros = ventes.filter(type_vente='gros')
    ventes_detail = ventes.filter(type_vente='detail')
    ventes_comptant = ventes.filter(mode_paiement='comptant')
    ventes_credit = ventes.filter(mode_paiement='credit')
    
    # Statistiques des stagiaires
    ventes_avec_stagiaire = ventes.filter(stagiaire__isnull=False)
    ventes_sans_stagiaire = ventes.filter(stagiaire__isnull=True)
    
    # Statistiques détaillées des stagiaires
    stats_stagiaires = ventes_avec_stagiaire.aggregate(
        total_ventes_stagiaires=Count('id'),
        chiffre_affaires_stagiaires=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
    )
    
    # Statistiques des ventes personnelles
    stats_personnel = ventes_sans_stagiaire.aggregate(
        chiffre_affaires_personnel=Sum(F('quantite') * F('prix_vente_unitaire'))
    )
    
    # ✅ CORRECTION : Gérer les valeurs None pour les statistiques stagiaires
    ventes_avec_stagiaire_count = stats_stagiaires['total_ventes_stagiaires'] or 0
    chiffre_affaires_stagiaires = stats_stagiaires['chiffre_affaires_stagiaires'] or Decimal('0.00')
    nombre_stagiaires_distincts = stats_stagiaires['nombre_stagiaires_distincts'] or 0
    chiffre_affaires_personnel = stats_personnel['chiffre_affaires_personnel'] or Decimal('0.00')
    
    # ✅ CORRECTION : Calcul sécurisé des pourcentages
    pourcentage_ventes_stagiaires = 0
    if total_ventes > 0:
        pourcentage_ventes_stagiaires = (ventes_avec_stagiaire_count / total_ventes) * 100
    
    pourcentage_ca_stagiaires = 0
    if chiffre_affaires_total > 0:
        pourcentage_ca_stagiaires = (chiffre_affaires_stagiaires / chiffre_affaires_total) * 100
    
    # Calculer les bonus obtenus
    bonus_obtenus = Decimal('0.00')
    dettes_avec_bonus = Dette.objects.filter(
        vente__agent=agent,
        bonus_accorde=True
    )
    for dette in dettes_avec_bonus:
        bonus_obtenus += dette.montant_bonus or Decimal('0.00')
    
    # Dettes en cours
    dettes_en_cours = Dette.objects.filter(
        vente__agent=agent,
        statut__in=['en_cours', 'partiellement_paye', 'en_retard']
    ).count()
    
    # ✅ CORRECTION : Requête pour les stagiaires actifs avec gestion des valeurs None
    stagiaires_actifs = Agent.objects.filter(
        type_agent='stagiaire',
        vente__agent=agent
    ).distinct().annotate(
        nombre_ventes=Count('vente'),
        total_ventes_ca=Sum(F('vente__quantite') * F('vente__prix_vente_unitaire'))
    ).order_by('-total_ventes_ca')
    
    # ✅ CORRECTION : Convertir les Decimal en float pour les templates si nécessaire
    context = {
        'ventes': ventes,
        'total_ventes': total_ventes,
        'chiffre_affaires_total': float(chiffre_affaires_total),
        'ventes_gros_count': ventes_gros.count(),
        'ventes_detail_count': ventes_detail.count(),
        'ventes_comptant_count': ventes_comptant.count(),
        'ventes_credit_count': ventes_credit.count(),
        'bonus_obtenus': float(bonus_obtenus),
        'dettes_en_cours': dettes_en_cours,
        'agent': agent,
        
        # Statistiques des stagiaires
        'ventes_avec_stagiaire_count': ventes_avec_stagiaire_count,
        'ventes_sans_stagiaire_count': ventes_sans_stagiaire.count(),
        'chiffre_affaires_stagiaires': float(chiffre_affaires_stagiaires),
        'chiffre_affaires_personnel': float(chiffre_affaires_personnel),
        'nombre_stagiaires_distincts': nombre_stagiaires_distincts,
        'pourcentage_ventes_stagiaires': pourcentage_ventes_stagiaires,
        'pourcentage_ca_stagiaires': pourcentage_ca_stagiaires,
        
        # Liste des stagiaires avec leurs performances
        'stagiaires_actifs': stagiaires_actifs,
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
            'specification': detail.specification or '',            
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

# views.py
# views.py
# versement

@login_required
def creer_versement(request):
    """Créer un versement - interface simple"""
    agent_connecte = request.user.agent
    
    if request.method == "POST":
        form = VersementForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # CORRECTION : Utiliser save() avec superviseur pour la création
                form.save(superviseur=agent_connecte)
                messages.success(request, "✅ Versement créé avec succès!")
                return redirect("liste_versement")
                    
            except Exception as e:
                messages.error(request, f"Erreur: {str(e)}")
    else:
        form = VersementForm()

    context = {
        "form": form, 
        "superviseur": agent_connecte
    }
    
    return render(request, "core/factures/creer_versement.html", context)


@login_required
def modifier_versement(request, versement_id):
    """Modifier un versement existant"""
    # Récupérer le versement
    versement = get_object_or_404(VersementBancaire, id=versement_id)
    
    # Vérifier les permissions
    if not hasattr(request.user, 'agent'):
        messages.error(request, "Accès réservé aux agents.")
        return redirect('login')
    
    user_agent = request.user.agent
    
    # Un superviseur ne peut modifier que ses propres versements
    # La direction peut modifier tous les versements
    if user_agent.est_superviseur and versement.superviseur != user_agent:
        messages.error(request, "Vous ne pouvez modifier que vos propres versements.")
        return redirect('liste_versements')
    
    if not (user_agent.est_superviseur or user_agent.est_direction):
        messages.error(request, "Accès non autorisé.")
        return redirect('liste_versements')
    
    # Récupérer la dépense existante s'il y en a une
    depense_existante = versement.depenses.first()
    
    if request.method == 'POST':
        form = VersementForm(request.POST, request.FILES, instance=versement)
        if form.is_valid():
            try:
                # CORRECTION : Utiliser save() sans superviseur pour la modification
                versement_modifie = form.save(superviseur=None, commit=True)
                
                # Gérer les dépenses (logique déjà dans save() maintenant)
                # Plus besoin de cette partie car gérée dans save()
                
                messages.success(request, "✅ Versement modifié avec succès!")
                return redirect('detail_versement', versement_id=versement.id)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de la modification: {str(e)}")
    else:
        # Pré-remplir le formulaire avec les données existantes
        initial_data = {}
        if depense_existante:
            initial_data = {
                'depense_montant': depense_existante.montant,
                'depense_description': depense_existante.description,
            }
        
        form = VersementForm(instance=versement, initial=initial_data)
    
    context = {
        'form': form,
        'versement': versement,
        'depense_existante': depense_existante,
    }
    
    return render(request, 'core/factures/modifier_versement.html', context)


@login_required
def liste_versement(request):
    """Afficher la liste des versements avec statistiques"""
    # Récupérer tous les versements
    versements = VersementBancaire.objects.all().order_by('-date_versement_reelle')
    
    # Calculer les statistiques
    total_vente = versements.aggregate(total=Sum('montant_vente'))['total'] or 0
    total_hors_vente = versements.aggregate(total=Sum('montant_hors_vente'))['total'] or 0
    total_general = total_vente + total_hors_vente
    
    context = {
        'versements': versements,
        'total_vente': total_vente,
        'total_hors_vente': total_hors_vente,
        'total_general': total_general,
    }
    
    return render(request, 'core/factures/liste_versement.html', context)

@login_required
def detail_versement(request, versement_id):
    """Afficher le détail d'un versement"""
    # Récupérer le versement
    versement = get_object_or_404(VersementBancaire, id=versement_id)
    
    # Vérifier les permissions
    if hasattr(request.user, 'agent'):
        user_agent = request.user.agent
        if not (user_agent.est_direction or user_agent.est_superviseur and versement.superviseur == user_agent):
            messages.error(request, "Vous n'avez pas accès à ce versement.")
            return redirect('liste_versements')
    
    # Récupérer les dépenses associées
    depenses = versement.depenses.all()
    
    # Calculer les statistiques
    total_depenses = versement.total_depenses_associees
    montant_net = versement.montant_total - total_depenses
    
    context = {
        'versement': versement,
        'depenses': depenses,
        'total_depenses': total_depenses,
        'montant_net': montant_net,
    }
    
    return render(request, 'core/factures/detail_versement.html', context)

# Dans views.py
from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages

from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages

class AjouterRecusView(UpdateView):
    model = VersementBancaire
    template_name = 'core/factures/ajouter_recus.html'
    fields = []  # Aucun champ du modèle principal
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recus'] = self.object.recus.all()
        context['versement'] = self.object  # Ajouter versement au contexte
        return context
    
    def form_valid(self, form):
        # Gérer l'upload de nouveaux reçus
        nouveaux_recus = self.request.FILES.getlist('nouveaux_recus')
        description = self.request.POST.get('description_recus', '').strip()
        
        if nouveaux_recus:
            for recu_file in nouveaux_recus:
                RecuVersement.objects.create(
                    versement=self.object,
                    fichier=recu_file,
                    description=description or f"Reçu supplémentaire pour versement {self.object.id}"
                )
            messages.success(self.request, f"{len(nouveaux_recus)} reçu(s) ajouté(s) avec succès!")
        else:
            messages.warning(self.request, "Aucun nouveau reçu sélectionné.")
        
        return super().form_valid(form)
    
    def get_success_url(self):
        # Utiliser le bon nom d'URL et le bon paramètre
        return reverse_lazy('detail_versement', kwargs={'versement_id': self.object.id})

@login_required
def supprimer_versement(request, versement_id):
    """Supprimer un versement existant"""
    try:
        # Récupérer le versement
        versement = get_object_or_404(VersementBancaire, id=versement_id)
        
        # Vérifier les permissions
        if not hasattr(request.user, 'agent'):
            messages.error(request, "Accès réservé aux agents.")
            return redirect('login')
        
        user_agent = request.user.agent
        
        # Vérification des permissions
        if user_agent.est_superviseur and versement.superviseur != user_agent:
            messages.error(request, "Vous ne pouvez supprimer que vos propres versements.")
            return redirect('liste_versement')
        
        if not (user_agent.est_superviseur or user_agent.est_direction):
            messages.error(request, "Accès non autorisé.")
            return redirect('liste_versement')
        
        if request.method == 'POST':
            # Sauvegarder les informations avant suppression
            versement_info = f"Versement #{versement.id} - {versement.montant_total} FCFA"
            
            # Supprimer le versement
            versement.delete()
            
            messages.success(request, f"✅ Versement {versement_info} supprimé avec succès!")
            return redirect('liste_versement')
        
        # Si méthode GET, afficher la page de confirmation
        context = {
            'versement': versement,
        }
        return render(request, 'core/factures/supprimer_versement.html', context)
        
    except VersementBancaire.DoesNotExist:
        messages.error(request, "❌ Le versement que vous essayez de supprimer n'existe pas.")
        return redirect('liste_versement')
    except Exception as e:
        messages.error(request, f"❌ Erreur inattendue: {str(e)}")
        return redirect('liste_versement')

from django.shortcuts import render, redirect
from .forms import RecuVersementForm

@login_required
def recu_liste(request):
    recus = RecuVersement.objects.all()
    return render(request, 'core/factures/recu_liste.html', {'recus': recus})

@login_required
def recu_create(request):
    if request.method == 'POST':
        form = RecuVersementForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                recus_crees = form.save()
                messages.success(
                    request, 
                    f"{len(recus_crees)} reçu(s) créé(s) avec succès !"
                )
                return redirect('recu_liste')
            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = RecuVersementForm()

    return render(request, 'core/factures/recu_form.html', {'form': form})


# views.py


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
    return render(request, 'core/factures/confirm_versement_delete.html', {'facture': facture})
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
        return redirect('dashboard_agent')
    
    # Un superviseur peut recouvrir ses propres ventes OU celles des agents terrain
    if agent_connecte.est_superviseur:
        if not (agent.est_agent_terrain or agent.id == agent_connecte.id):
            messages.error(request, "Vous ne pouvez recouvrir que vos propres ventes ou celles de vos agents terrain.")
            return redirect('tableau_de_bord_superviseur')
    
    # Un directeur peut recouvrir tout le monde
    if agent_connecte.est_direction:
        if not (agent.est_agent_terrain or agent.est_superviseur):
            messages.error(request, "Vous ne pouvez recouvrir que les agents terrain et superviseurs.")
            return redirect('tableaulo_de_bord')
    
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
        agents = Agent.objects.filter(type_agent__in=['terrain', 'entrepot'])
    elif agent_connecte.est_superviseur:
        agents_terrain = Agent.objects.filter(type_agent='terrain')
        agents = list(agents_terrain) + [agent_connecte]
    else:
        agents = []
    
    agents_data = []
    
    # TOTAUX SIMPLIFIÉS
    total_ventes_tous_agents = 0
    total_recouvre_tous_agents = 0
    
    for agent in agents:
        if agent.est_superviseur:
            # SUPERVISEUR : ses ventes sont déjà recouvrées (auto-recouvrement)
            total_ventes = agent.total_ventes  # Ventes directes du superviseur
            total_recouvre = agent.total_ventes  # Auto-recouvré immédiatement
            difference = 0  # Toujours à jour car auto-recouvré
            depenses = agent.total_depenses_superviseur
            
            # Statut superviseur
            couleur, statut = 'success', 'À jour (auto-recouvré)'
                
        else:
            # AGENT TERRAIN : logique normale
            total_ventes = agent.total_ventes
            total_recouvre = agent.total_recouvre
            difference = total_ventes - total_recouvre
            depenses = 0
            
            # Statut agent terrain
            if difference == 0:
                couleur, statut = 'success', 'Complètement recouvré'
            elif difference > 0:
                couleur, statut = 'warning', f'{difference:,.0f} FCFA à recouvrir'
            else:
                couleur, statut = 'danger', 'Erreur de calcul'
        
        # Accumuler les totaux
        total_ventes_tous_agents += total_ventes
        total_recouvre_tous_agents += total_recouvre
        
        agents_data.append({
            'agent': agent,
            'total_ventes': total_ventes,
            'total_recouvre': total_recouvre,
            'depenses': depenses,
            'difference': difference,
            'couleur': couleur,
            'statut': statut,
            'est_auto_recouvrement': agent.id == agent_connecte.id,
            'est_superviseur': agent.est_superviseur,
        })
    
    # TOTAUX GÉNÉRAUX CLAIRS
    reste_a_recouvrir = total_ventes_tous_agents - total_recouvre_tous_agents
    
    # État du superviseur connecté (si c'est un superviseur)
    etat_superviseur = None
    if agent_connecte.est_superviseur:
        etat_superviseur = {
            'total_ventes_personnelles': agent_connecte.total_ventes,
            'total_depenses': agent_connecte.total_depenses_superviseur,
            'total_versements_bancaires': agent_connecte.total_versements_bancaires,
            'solde_actuel': agent_connecte.solde_superviseur,
            'dernier_versement': agent_connecte.dernier_versement_superviseur,
        }
    
    context = {
        'agents_data': agents_data,
        'total_ventes_tous_agents': total_ventes_tous_agents,
        'total_recouvre_tous_agents': total_recouvre_tous_agents,
        'reste_a_recouvrir': reste_a_recouvrir,
        'agent_connecte': agent_connecte,
        'etat_superviseur': etat_superviseur,
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
        redirect('login')
    
    # ✅ CORRECTION : Définir date_debut_recent AU DÉBUT de la fonction
    date_debut_recent = timezone.now() - timedelta(days=30)
    
    # Vue Stock
    stock_total = LotEntrepot.objects.filter(quantite_restante__gt=0).aggregate(
        total_quantite=Sum('quantite_restante'),
        total_valeur=Sum(F('quantite_restante') * F('prix_achat_unitaire'))
    )
    
    produits_stock = LotEntrepot.objects.filter(
        quantite_restante__gt=0
    ).select_related('produit').values(
        'produit__nom'
    ).annotate(
        quantite_totale=Sum('quantite_restante'),
        valeur_totale=Sum(F('quantite_restante') * F('prix_achat_unitaire'))
    ).order_by('-quantite_totale')
    
    # Vue Agents - TOUTES LES PÉRIODES
    agents_terrain = Agent.objects.filter(type_agent='terrain').select_related('user')
    
    performances_agents = []
    for agent in agents_terrain:
        # SUPPRIMER le filtre de date - TOUTES LES VENTES
        ventes_agent_toutes = Vente.objects.filter(agent=agent)  # ← Pas de filtre date
        
        # Utiliser aggregate() pour toutes les ventes
        stats_ventes = ventes_agent_toutes.aggregate(
            total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
            nombre_ventes=Count('id'),
            clients_distincts=Count('client', distinct=True),
            quantite_vendue=Sum('quantite'),
            ventes_gros=Sum(F('quantite') * F('prix_vente_unitaire'), filter=Q(type_vente='gros')),
            ventes_detail=Sum(F('quantite') * F('prix_vente_unitaire'), filter=Q(type_vente='detail'))
        )
        
        # ✅ NOUVEAU : Statistiques des stagiaires pour cet agent
        ventes_stagiaires_agent = Vente.objects.filter(agent=agent, stagiaire__isnull=False)
        stats_stagiaires = ventes_stagiaires_agent.aggregate(
            total_ventes_stagiaires=Sum(F('quantite') * F('prix_vente_unitaire')),
            nombre_ventes_stagiaires=Count('id'),
            nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
        )
        
        # ✅ CORRECTION : date_debut_recent est maintenant définie au début
        distributions_recentes = DistributionAgent.objects.filter(
            agent_terrain=agent,
            date_distribution__gte=date_debut_recent
        ).aggregate(
            total_produits=Sum('quantite_totale')
        )
        
        performances_agents.append({
            'agent': agent,
            'total_ventes': stats_ventes['total_ventes'] or 0,
            'ventes_gros': stats_ventes['ventes_gros'] or 0,
            'ventes_detail': stats_ventes['ventes_detail'] or 0,
            'nombre_ventes': stats_ventes['nombre_ventes'] or 0,
            'clients_distincts': stats_ventes['clients_distincts'] or 0,
            'quantite_vendue': stats_ventes['quantite_vendue'] or 0,
            'produits_distribues_recent': distributions_recentes['total_produits'] or 0,
            
            # ✅ NOUVEAU : Statistiques stagiaires
            'total_ventes_stagiaires': stats_stagiaires['total_ventes_stagiaires'] or 0,
            'nombre_ventes_stagiaires': stats_stagiaires['nombre_ventes_stagiaires'] or 0,
            'nombre_stagiaires_distincts': stats_stagiaires['nombre_stagiaires_distincts'] or 0,
            'total_ventes_personnelles': (stats_ventes['total_ventes'] or 0) - (stats_stagiaires['total_ventes_stagiaires'] or 0),
            
            # Propriétés historiques de l'agent
            'total_ventes_historique': agent.total_ventes,
            'total_recouvre': agent.total_recouvre,
            'argent_en_possession': agent.argent_en_possession,
            'peut_etre_recouvre': agent.peut_etre_recouvre,
        })
    
    # VUE VENTES GLOBALES - TOUTES LES PÉRIODES
    ventes_toutes_queryset = Vente.objects.all()  # ← Pas de filtre date
    
    stats_ventes_global = ventes_toutes_queryset.aggregate(
        total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes=Count('id'),
        quantite_vendue=Sum('quantite'),
        ventes_gros=Sum(F('quantite') * F('prix_vente_unitaire'), filter=Q(type_vente='gros')),
        ventes_detail=Sum(F('quantite') * F('prix_vente_unitaire'), filter=Q(type_vente='detail')),
        ventes_credit=Count('id', filter=Q(mode_paiement='credit')),
        ventes_comptant=Count('id', filter=Q(mode_paiement='comptant'))
    )
    
    # ✅ NOUVEAU : Statistiques globales des stagiaires
    stats_ventes_stagiaires_global = Vente.objects.filter(stagiaire__isnull=False).aggregate(
        total_ventes_stagiaires=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes_stagiaires=Count('id'),
        nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
    )
    
    ventes_global = {
        'total_ventes': stats_ventes_global['total_ventes'] or 0,
        'ventes_gros': stats_ventes_global['ventes_gros'] or 0,
        'ventes_detail': stats_ventes_global['ventes_detail'] or 0,
        'nombre_ventes': stats_ventes_global['nombre_ventes'] or 0,
        'quantite_vendue': stats_ventes_global['quantite_vendue'] or 0,
        'ventes_credit': stats_ventes_global['ventes_credit'] or 0,
        'ventes_comptant': stats_ventes_global['ventes_comptant'] or 0,
        # ✅ NOUVEAU : Ajout des stats stagiaires globales
        'total_ventes_stagiaires': stats_ventes_stagiaires_global['total_ventes_stagiaires'] or 0,
        'nombre_ventes_stagiaires': stats_ventes_stagiaires_global['nombre_ventes_stagiaires'] or 0,
        'nombre_stagiaires_distincts': stats_ventes_stagiaires_global['nombre_stagiaires_distincts'] or 0,
        'total_ventes_personnelles': (stats_ventes_global['total_ventes'] or 0) - (stats_ventes_stagiaires_global['total_ventes_stagiaires'] or 0),
    }
    
    # Ventes par type - TOUTES LES PÉRIODES
    ventes_par_type = Vente.objects.all().values(
        'type_vente'
    ).annotate(
        total=Sum(F('quantite') * F('prix_vente_unitaire')),
        count=Count('id'),
        quantite=Sum('quantite')
    )
    
    # VUE PERSONNELLE SUPERVISEUR - TOUTES LES PÉRIODES
    ventes_superviseur_queryset = Vente.objects.filter(agent=superviseur)
    
    stats_ventes_superviseur = ventes_superviseur_queryset.aggregate(
        total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes=Count('id'),
        quantite_vendue=Sum('quantite'),
        ventes_gros=Sum(F('quantite') * F('prix_vente_unitaire'), filter=Q(type_vente='gros')),
        ventes_detail=Sum(F('quantite') * F('prix_vente_unitaire'), filter=Q(type_vente='detail'))
    )
    
    # ✅ NOUVEAU : Statistiques stagiaires pour le superviseur
    stats_stagiaires_superviseur = Vente.objects.filter(agent=superviseur, stagiaire__isnull=False).aggregate(
        total_ventes_stagiaires=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes_stagiaires=Count('id'),
        nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
    )
    
    ventes_superviseur = {
        'total_ventes': stats_ventes_superviseur['total_ventes'] or 0,
        'ventes_gros': stats_ventes_superviseur['ventes_gros'] or 0,
        'ventes_detail': stats_ventes_superviseur['ventes_detail'] or 0,
        'nombre_ventes': stats_ventes_superviseur['nombre_ventes'] or 0,
        'quantite_vendue': stats_ventes_superviseur['quantite_vendue'] or 0,
        # ✅ NOUVEAU : Ajout des stats stagiaires superviseur
        'total_ventes_stagiaires': stats_stagiaires_superviseur['total_ventes_stagiaires'] or 0,
        'nombre_ventes_stagiaires': stats_stagiaires_superviseur['nombre_ventes_stagiaires'] or 0,
        'nombre_stagiaires_distincts': stats_stagiaires_superviseur['nombre_stagiaires_distincts'] or 0,
        'total_ventes_personnelles': (stats_ventes_superviseur['total_ventes'] or 0) - (stats_stagiaires_superviseur['total_ventes_stagiaires'] or 0),
    }
    
    # ✅ CORRECTION : date_debut_recent est maintenant disponible
    distributions_superviseur = DistributionAgent.objects.filter(
        Q(superviseur=superviseur) | Q(agent_terrain=superviseur),
        date_distribution__gte=date_debut_recent
    ).count()
    
    # STATISTIQUES SUPERVISEUR
    stats_superviseur = {
        'total_recouvrements': superviseur.total_argent_recouvre_et_ventes,
        'total_depenses': superviseur.total_depenses_vente,  # ← CORRECTION
        'total_versements': superviseur.total_versements_vente,  # ← CORRECTION
        'solde_actuel': superviseur.solde_vente_superviseur,  # ← CORRECTION
        'dernier_versement': superviseur.dernier_versement_superviseur,
        'versements_recents': superviseur.versements_recents_superviseur,
        # ✅ NOUVEAU : Ajout des stats stagiaires du superviseur
        'total_ventes_stagiaires': superviseur.total_ventes_stagiaires,
        'total_ventes_personnelles': superviseur.total_ventes_personnelles,
        'nombre_stagiaires_supervises': superviseur.nombre_stagiaires_supervises,
    }
    
    # Alertes stock faible
    seuil_stock_faible = 10
    stocks_faibles = LotEntrepot.objects.filter(
        quantite_restante__lte=seuil_stock_faible,
        quantite_restante__gt=0
    ).select_related('produit')
    
    # Dettes en cours
    dettes_en_cours = Dette.objects.filter(
        statut__in=['en_cours', 'partiellement_paye']
    ).count()
    
    # RÉCAPITULATIF FINANCIER - TOUTES PÉRIODES
    total_ventes_agents = sum(agent['total_ventes'] for agent in performances_agents)
    total_ventes_superviseur_calc = ventes_superviseur['total_ventes']
    total_ventes_global_calc = total_ventes_agents + total_ventes_superviseur_calc
    
    # ✅ NOUVEAU : Calculs stagiaires
    total_ventes_stagiaires_agents = sum(agent['total_ventes_stagiaires'] for agent in performances_agents)
    total_ventes_personnelles_agents = sum(agent['total_ventes_personnelles'] for agent in performances_agents)
    
    # Vérification que les totaux correspondent
    ecart = abs(total_ventes_global_calc - ventes_global['total_ventes'])
    correspond = ecart < 0.01  # Tolérance de 0.01 FCFA
    
    recapitulatif_financier = {
        'valeur_stock_total': stock_total['total_valeur'] or 0,
        'ventes_total': ventes_global['total_ventes'],
        'total_a_recouvrer': sum(agent['argent_en_possession'] for agent in performances_agents),
        'dettes_en_cours_count': dettes_en_cours,
        'verification_ventes': {
            'total_agents': total_ventes_agents,
            'total_superviseur': total_ventes_superviseur_calc,
            'total_global_calc': total_ventes_global_calc,
            'total_global_direct': ventes_global['total_ventes'],
            'ecart': ecart,
            'correspond': correspond
        },
        # ✅ NOUVEAU : Ajout des stats stagiaires
        'total_ventes_stagiaires': total_ventes_stagiaires_agents + ventes_superviseur['total_ventes_stagiaires'],
        'total_ventes_personnelles': total_ventes_personnelles_agents + ventes_superviseur['total_ventes_personnelles'],
        'pourcentage_ventes_stagiaires': ((total_ventes_stagiaires_agents + ventes_superviseur['total_ventes_stagiaires']) / ventes_global['total_ventes'] * 100) if ventes_global['total_ventes'] > 0 else 0,
    }
    
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
        
        # Données ventes globales - TOUTES PÉRIODES
        'ventes_global': ventes_global,
        'ventes_par_type': ventes_par_type,
        
        # Données personnelles superviseur
        'ventes_superviseur': ventes_superviseur,
        'distributions_superviseur': distributions_superviseur,
        'stats_superviseur': stats_superviseur,
        
        # Alertes
        'dettes_en_cours': dettes_en_cours,
        
        # Récapitulatif
        'recapitulatif_financier': recapitulatif_financier,
        
        # ✅ CORRECTION : Ajouter la date pour le template si nécessaire
        'date_debut_recent': date_debut_recent,
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
      
    ).order_by('-date_distribution')
    
    # Ventes de l'agent avec filtrage par période
    ventes = Vente.objects.filter(
        agent=agent,
        
    ).select_related('client', 'detail_distribution__lot__produit').order_by('-date_vente')
    
    # Statistiques générales (sans Coalesce)
    stats_ventes_raw = ventes.aggregate(
        total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
        nombre_ventes=Count('id'),
        quantite_vendue=Sum('quantite')
    )
    
    # Convertir les None en 0
    stats_ventes = {
        'total_ventes': stats_ventes_raw['total_ventes'] or 0,
        'nombre_ventes': stats_ventes_raw['nombre_ventes'] or 0,
        'quantite_vendue': stats_ventes_raw['quantite_vendue'] or 0,
    }
    
    # Statistiques détaillées par type de vente
    ventes_gros = ventes.filter(type_vente='gros')
    ventes_detail = ventes.filter(type_vente='detail')
    
    stats_gros_raw = ventes_gros.aggregate(
        total=Sum(F('quantite') * F('prix_vente_unitaire')),
        quantite=Sum('quantite'),
        nombre=Count('id')
    )
    
    stats_detail_raw = ventes_detail.aggregate(
        total=Sum(F('quantite') * F('prix_vente_unitaire')),
        quantite=Sum('quantite'),
        nombre=Count('id')
    )
    
    stats_gros = {
        'total': stats_gros_raw['total'] or 0,
        'quantite': stats_gros_raw['quantite'] or 0,
        'nombre': stats_gros_raw['nombre'] or 0,
    }
    
    stats_detail = {
        'total': stats_detail_raw['total'] or 0,
        'quantite': stats_detail_raw['quantite'] or 0,
        'nombre': stats_detail_raw['nombre'] or 0,
    }
    
    # Dettes de l'agent
    dettes = Dette.objects.filter(
        vente__agent=agent,
        statut__in=['en_cours', 'partiellement_paye', 'en_retard']
    ).select_related('vente__client')
    
    # Recouvrements pour cet agent
    recouvrements = Recouvrement.objects.filter(
        agent=agent,
      
    ).order_by('-date_recouvrement')
    
    total_recouvre_raw = recouvrements.aggregate(total=Sum('montant_recouvre'))
    total_recouvre = total_recouvre_raw['total'] or 0
    
    # Calculer le solde à recouvrer pour cette période
    total_ventes_periode = stats_ventes['total_ventes']
    solde_a_recouvrer_periode = total_ventes_periode - total_recouvre
    
    context = {
        'superviseur': superviseur,
        'agent_cible': agent,
        'distributions': distributions,
        'ventes': ventes[:10],  # 10 dernières ventes
        'stats_ventes': stats_ventes,
        'stats_gros': stats_gros,
        'stats_detail': stats_detail,
        'dettes': dettes,
        'recouvrements': recouvrements,
        'total_recouvre': total_recouvre,
        'solde_a_recouvrer_periode': solde_a_recouvrer_periode,
        'date_debut': date_debut,
    }
    
    return render(request, 'core/dashboard/detail_agent.html', context)

from django.db.models import DecimalField
from django.db.models.functions import Coalesce

@login_required
def detail_stagiaire(request, stagiaire_id):
    """Vue détaillée d'un stagiaire avec ses statistiques de vente"""
    try:
        # Récupérer le superviseur connecté
        superviseur = Agent.objects.get(user=request.user, type_agent='entrepot')
    except Agent.DoesNotExist:
        messages.error(request, "Accès réservé aux superviseurs.")
        return redirect('dashboard')
    
    # Récupérer le stagiaire
    stagiaire = get_object_or_404(Agent, id=stagiaire_id, type_agent='stagiaire')
    
    # Récupérer toutes les ventes attribuées à ce stagiaire
    ventes_stagiaire = Vente.objects.filter(
        stagiaire=stagiaire
    ).select_related(
        'client', 'detail_distribution__lot__produit', 'agent'
    ).order_by('-date_vente')
    
    # ✅ APPROCHE SIMPLE : Calcul manuel des totaux
    total_ventes = sum(vente.total_vente for vente in ventes_stagiaire)
    quantite_vendue = sum(vente.quantite for vente in ventes_stagiaire)
    nombre_ventes = ventes_stagiaire.count()
    nombre_clients = ventes_stagiaire.values('client').distinct().count()
    
    stats_ventes = {
        'total_ventes': total_ventes,
        'nombre_ventes': nombre_ventes,
        'quantite_vendue': quantite_vendue,
        'nombre_clients': nombre_clients,
    }
    
    # ✅ APPROCHE SIMPLE : Filtrage manuel par type
    ventes_gros = [v for v in ventes_stagiaire if v.type_vente == 'gros']
    ventes_detail = [v for v in ventes_stagiaire if v.type_vente == 'detail']
    
    stats_gros = {
        'total': sum(v.total_vente for v in ventes_gros),
        'quantite': sum(v.quantite for v in ventes_gros),
        'nombre': len(ventes_gros),
    }
    
    stats_detail = {
        'total': sum(v.total_vente for v in ventes_detail),
        'quantite': sum(v.quantite for v in ventes_detail),
        'nombre': len(ventes_detail),
    }
    
    # ✅ APPROCHE SIMPLE : Mode de paiement
    ventes_comptant = [v for v in ventes_stagiaire if v.mode_paiement == 'comptant']
    ventes_credit = [v for v in ventes_stagiaire if v.mode_paiement == 'credit']
    
    stats_comptant = {
        'total': sum(v.total_vente for v in ventes_comptant),
        'nombre': len(ventes_comptant),
    }
    
    stats_credit = {
        'total': sum(v.total_vente for v in ventes_credit),
        'nombre': len(ventes_credit),
    }
    
    # ✅ APPROCHE SIMPLE : Produits les plus vendus
    from collections import defaultdict
    produits_dict = defaultdict(lambda: {'quantite_vendue': 0, 'chiffre_affaire': 0, 'nombre_ventes': 0})
    
    for vente in ventes_stagiaire:
        produit_nom = vente.produit_nom
        produits_dict[produit_nom]['quantite_vendue'] += vente.quantite
        produits_dict[produit_nom]['chiffre_affaire'] += vente.total_vente
        produits_dict[produit_nom]['nombre_ventes'] += 1
    
    produits_vendus = [
        {
            'detail_distribution__lot__produit__nom': nom,
            'quantite_vendue': data['quantite_vendue'],
            'chiffre_affaire': data['chiffre_affaire'],
            'nombre_ventes': data['nombre_ventes']
        }
        for nom, data in produits_dict.items()
    ]
    produits_vendus.sort(key=lambda x: x['quantite_vendue'], reverse=True)
    produits_vendus = produits_vendus[:5]
    
    # ✅ APPROCHE SIMPLE : Tuteurs
    tuteurs_dict = defaultdict(lambda: {'nombre_ventes': 0, 'total_ventes': 0})
    
    for vente in ventes_stagiaire:
        tuteur_nom = f"{vente.agent.user.first_name} {vente.agent.user.last_name}"
        tuteurs_dict[tuteur_nom]['nombre_ventes'] += 1
        tuteurs_dict[tuteur_nom]['total_ventes'] += vente.total_vente
    
    tuteurs = [
        {
            'agent__user__first_name': vente.agent.user.first_name,
            'agent__user__last_name': vente.agent.user.last_name,
            'agent__type_agent': vente.agent.type_agent,
            'nombre_ventes': data['nombre_ventes'],
            'total_ventes': data['total_ventes']
        }
        for vente in ventes_stagiaire  # Pour récupérer les infos agent
        for nom, data in tuteurs_dict.items()
        if f"{vente.agent.user.first_name} {vente.agent.user.last_name}" == nom
    ]
    # Éliminer les doublons
    tuteurs = list({t['agent__user__first_name'] + t['agent__user__last_name']: t for t in tuteurs}.values())
    tuteurs.sort(key=lambda x: x['nombre_ventes'], reverse=True)
    
    context = {
        'superviseur': superviseur,
        'stagiaire': stagiaire,
        'ventes': ventes_stagiaire[:10],
        'stats_ventes': stats_ventes,
        'stats_gros': stats_gros,
        'stats_detail': stats_detail,
        'stats_comptant': stats_comptant,
        'stats_credit': stats_credit,
        'produits_vendus': produits_vendus,
        'tuteurs': tuteurs,
        'total_tuteurs': len(tuteurs),
    }
    
    return render(request, 'core/dashboard/detail_stagiaire.html', context)
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

# core/views/dashboard.py
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.services.dashboard_service import DashboardService

# core/views.py

# core/views/dashboard.py
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.services.dashboard_service import DashboardService

# core/views/dashboard.py
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/analyses/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupération des paramètres de filtre
        periode_type = self.request.GET.get('periode', 'mois')
        annee = self.request.GET.get('annee')
        mois = self.request.GET.get('mois')
        
        # Conversion des paramètres
        if annee:
            annee = int(annee)
        if mois:
            mois = int(mois)
        
        # 🔵 Bloc 1 : KPIs Globaux
        kpis_globaux = DashboardService.get_kpis_globaux(periode_type, annee, mois)
        
        # 🟣 Bloc 2 : Stock ESSENTIEL avec fournisseurs
        stock_essentiel = DashboardService.get_stock_essentiel_avec_fournisseurs()
        
        # 🟠 Bloc 3 : Performances Agents
        performances_agents = DashboardService.get_performances_agents(periode_type, annee, mois)
        
        # 🔴 Bloc 4 : Analyses Ventes AVANCÉES
        analyses_ventes = DashboardService.get_analyses_ventes_avancees(periode_type, annee, mois)
        
        # 🟢 Bloc 5 : Analyses Dépenses
        analyses_depenses = DashboardService.get_analyses_depenses(periode_type, annee, mois)
        
        # 🟦 Bloc 6 : Portefeuilles de TOUS les superviseurs (pour la direction)
        portefeuilles_superviseurs = []
        user_has_agent = hasattr(self.request.user, 'agent')
        user_is_direction = False
        
        if user_has_agent:
            user_is_direction = self.request.user.agent.est_direction
            if user_is_direction:
                portefeuilles_superviseurs = DashboardService.get_portefeuilles_tous_superviseurs(
                    periode_type, annee, mois
                )
        
        # Années disponibles pour le filtre
        annees_disponibles = DashboardService.get_annees_disponibles()
        
        context.update({
            # KPI Globaux
            **kpis_globaux,
            
            # Stock ESSENTIEL avec fournisseurs
            'stock_essentiel': stock_essentiel,
            
            # Performances
            'performances_agents': performances_agents,
            
            # Ventes
            **analyses_ventes,
            
            # Dépenses
            **analyses_depenses,
            
            # Portefeuilles superviseurs (pour la direction)
            'portefeuilles_superviseurs': portefeuilles_superviseurs,
            'user_has_agent': user_has_agent,
            'user_is_direction': user_is_direction,
            
            # Filtres
            'annees_disponibles': annees_disponibles,
            'periode_selectionnee': periode_type,
            'annee_selectionnee': annee,
            'mois_selectionne': mois,
            'mois_liste': [
                (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
                (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
                (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
            ]
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
        
        for vente in Vente.objects.select_related('detail_distribution__lot__produit', 'client', 'agent'):
            # Vérification que le produit existe
            if not vente.detail_distribution or not vente.detail_distribution.lot or not vente.detail_distribution.lot.produit:
                continue
                
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
            
            # Gestion des clients (peut être None)
            if vente.client and vente.client.id:
                data['clients_count'].add(vente.client.id)
            
            # Gestion des agents (toujours présent normalement)
            if vente.agent and vente.agent.id:
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
            if not lot.produit:
                continue
                
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
            
            # Calculs détaillés - TOUT en Decimal pour éviter les conflits
            ca_total = Decimal('0.00')
            ca_mois = Decimal('0.00')
            ca_trimestre = Decimal('0.00')
            quantite_total = Decimal('0.00')
            clients_servis = set()
            produits_vendus = set()
            montants_ventes = []
            
            for vente in ventes_agent:
                montant = vente.quantite * vente.prix_vente_unitaire  # Garder en Decimal
                ca_total += montant
                quantite_total += vente.quantite
                
                # Gestion des clients (peut être None)
                if vente.client and vente.client.id:
                    clients_servis.add(vente.client.id)
                
                # Gestion des produits
                if (vente.detail_distribution and 
                    vente.detail_distribution.lot and 
                    vente.detail_distribution.lot.produit):
                    produits_vendus.add(vente.detail_distribution.lot.produit.nom)
                
                montants_ventes.append(float(montant))  # Convertir en float seulement pour la liste
                
                if vente.date_vente >= debut_mois:
                    ca_mois += montant
                if vente.date_vente >= debut_trimestre:
                    ca_trimestre += montant
            
            # Indicateurs de performance - convertir en float pour les calculs
            nombre_ventes = ventes_agent.count()
            panier_moyen = float(ca_total) / nombre_ventes if nombre_ventes > 0 else 0
            efficacite = float(ca_total) / len(clients_servis) if clients_servis else 0
            
            # Taux de conversion (basé sur les distributions)
            distributions_agent = DistributionAgent.objects.filter(agent_terrain=agent)
            quantite_distribuee = sum(
                float(detail.quantite) for dist in distributions_agent 
                for detail in dist.detaildistribution_set.all()
            )
            taux_conversion = (float(quantite_total) / quantite_distribuee * 100) if quantite_distribuee > 0 else 0
            
            # Performance temporelle
            if nombre_ventes > 0:
                try:
                    premiere_vente = ventes_agent.earliest('date_vente')
                    anciennete_jours = (today - premiere_vente.date_vente).days
                    ventes_par_jour = nombre_ventes / anciennete_jours if anciennete_jours > 0 else 0
                except Vente.DoesNotExist:
                    ventes_par_jour = 0
            else:
                ventes_par_jour = 0
            
            # Dettes et recouvrement
            dettes_agent = Dette.objects.filter(vente__agent=agent)
            dettes_actives = dettes_agent.exclude(statut='paye')
            taux_recouvrement = (
                (dettes_agent.filter(statut='paye').count() / dettes_agent.count() * 100) 
                if dettes_agent.count() > 0 else 100
            )
            
            # Score de performance composite - utiliser les valeurs float
            ca_mois_float = float(ca_mois)
            score_performance = (
                (ca_mois_float / max(ca_mois_float, 1)) * 40 +  # Poids CA: 40%
                (taux_conversion / 100) * 30 +                  # Poids conversion: 30%
                (taux_recouvrement / 100) * 20 +                # Poids recouvrement: 20%
                (len(clients_servis) / max(len(clients_servis), 1)) * 10  # Poids clientèle: 10%
            )
            
            agents_analyse.append({
                'agent': agent,
                'ca_total': float(ca_total),  # Convertir en float pour le template
                'ca_mois': float(ca_mois),
                'ca_trimestre': float(ca_trimestre),
                'quantite_total': float(quantite_total),
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
                
                # Calcul en Decimal puis conversion en float
                ca_mois_ref = sum(v.quantite * v.prix_vente_unitaire for v in ventes_mois_ref)
                clients_mois_ref = ventes_mois_ref.values('client').distinct().count()
                
                evolution_data.append({
                    'mois': debut_mois_ref.strftime('%b %Y'),
                    'ca': float(ca_mois_ref),  # Convertir en float
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

