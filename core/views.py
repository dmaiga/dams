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
from django.contrib.auth.views import LogoutView

from django.db.models import F, Sum, Count, DecimalField

from django.shortcuts import render, get_object_or_404, redirect
from .models import Facture
from .forms import FactureForm
from django.contrib import messages

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone

# views.py
from django.db.models import Count, Sum, Avg, F, Q, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta
from django.views.generic import TemplateView
# views.py
from django.db.models import Count, Sum, Avg, F, Q, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta
from django.views.generic import TemplateView
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_user(request):
    logout(request)  
    return redirect('login') 

    
#=========
#DASHBOARD
#========


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'
    
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
    
# views.py
class PerformanceAgentsView(LoginRequiredMixin, TemplateView):
    template_name = 'core/statistiques/stat_agents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Périodes
        today = timezone.now()
        debut_mois = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_semaine = today - timedelta(days=today.weekday())
        
        # === PERFORMANCE GLOBALE DES AGENTS ===
        agents_performance = []
        agents = Agent.objects.filter(type_agent='terrain').select_related('user')
        
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
            
            for vente in ventes_agent:
                montant = float(vente.quantite * vente.prix_vente_unitaire)
                ca_total += montant
                quantite_total += vente.quantite
            
            for vente in ventes_mois:
                ca_mois += float(vente.quantite * vente.prix_vente_unitaire)
                
            for vente in ventes_semaine:
                ca_semaine += float(vente.quantite * vente.prix_vente_unitaire)
            
            # Clients servis
            clients_servis = ventes_agent.values('client').distinct().count()
            clients_mois = ventes_mois.values('client').distinct().count()
            
            # Efficacité commerciale (CA moyen par vente)
            efficacite = ca_total / ventes_agent.count() if ventes_agent.count() > 0 else 0
            
            # Objectifs (vous pouvez personnaliser cette logique)
            objectif_mensuel = 500000  # 500,000 FCFA par défaut
            taux_objectif = (ca_mois / objectif_mensuel * 100) if objectif_mensuel > 0 else 0
            
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
                'efficacite': efficacite,
                'objectif_mensuel': objectif_mensuel,
                'taux_objectif': taux_objectif,
                'panier_moyen': ca_total / ventes_agent.count() if ventes_agent.count() > 0 else 0,
            })
        
        # Trier par CA du mois (performance)
        agents_performance.sort(key=lambda x: x['ca_mois'], reverse=True)
        
        # === STATISTIQUES GLOBALES ===
        total_agents = len(agents_performance)
        ca_mois_total = sum(agent['ca_mois'] for agent in agents_performance)
        ca_total_global = sum(agent['ca_total'] for agent in agents_performance)
        moyenne_efficacite = sum(agent['efficacite'] for agent in agents_performance) / total_agents if total_agents > 0 else 0
        moyenne_objectif = sum(agent['taux_objectif'] for agent in agents_performance) / total_agents if total_agents > 0 else 0
        
        # === TOP PERFORMERS ===
        top_performers_mois = sorted(agents_performance, key=lambda x: x['ca_mois'], reverse=True)[:3]
        top_performers_clients = sorted(agents_performance, key=lambda x: x['clients_servis'], reverse=True)[:3]
        top_performers_efficacite = sorted(agents_performance, key=lambda x: x['efficacite'], reverse=True)[:3]
        
        # === ÉVOLUTION MENSUELLE PAR AGENT ===
        evolution_agents = {}
        evolution_months = []  # Pour stocker les mois une seule fois
        
        # Récupérer les mois une fois pour toutes
        for i in range(6):  # 6 derniers mois
            mois_date = today - timedelta(days=30*i)
            debut_mois_ref = mois_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            evolution_months.append({
                'mois': debut_mois_ref.strftime('%b %Y'),
                'date': debut_mois_ref
            })
        
        evolution_months.reverse()  # De l'ancien au récent
        
        for agent_perf in agents_performance[:5]:  # Top 5 agents seulement pour éviter la surcharge
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
                for vente in ventes_mois_ref:
                    ca_mois_ref += float(vente.quantite * vente.prix_vente_unitaire)
                
                evolution_data.append({
                    'mois': month_data['mois'],
                    'ca': ca_mois_ref
                })
            
            evolution_agents[agent.user.get_full_name()] = evolution_data
        
        context.update({
            'agents_performance': agents_performance,
            'total_agents': total_agents,
            'ca_mois_total': ca_mois_total,
            'ca_total_global': ca_total_global,
            'moyenne_efficacite': moyenne_efficacite,
            'moyenne_objectif': moyenne_objectif,
            'top_performers_mois': top_performers_mois,
            'top_performers_clients': top_performers_clients,
            'top_performers_efficacite': top_performers_efficacite,
            'evolution_agents': evolution_agents,
            'evolution_months': evolution_months,  # Ajout des mois séparément
        })
        
        return context
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
    
    return render(request, 'core/dashboard_agent.html', context)
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

@login_required
def liste_distributions(request):
    """Liste toutes les distributions avec valeurs gros et détail"""
    distributions = DistributionAgent.objects.all().order_by('-date_distribution')
    
    total_quantite = 0
    total_valeur_gros = 0
    total_valeur_detail = 0
    agents_distincts = set()
    produits_distincts = set()
    
    for dist in distributions:
        details = dist.detaildistribution_set.all()
        dist.quantite_totale = sum(detail.quantite for detail in details)
        dist.valeur_attendue_gros = sum((detail.prix_gros or 0) * detail.quantite for detail in details)
        dist.valeur_attendue_detail = sum((detail.prix_detail or 0) * detail.quantite for detail in details)
        
        total_quantite += dist.quantite_totale
        total_valeur_gros += dist.valeur_attendue_gros
        total_valeur_detail += dist.valeur_attendue_detail
        
        agents_distincts.add(dist.agent_terrain)
        for detail in details:
            produits_distincts.add(detail.lot.produit)
    
    context = {
        'distributions': distributions,
        'total_distributions': distributions.count(),
        'total_quantite': total_quantite,
        'total_valeur_gros': total_valeur_gros,
        'total_valeur_detail': total_valeur_detail,
        'total_agents': len(agents_distincts),
        'total_produits': len(produits_distincts),
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
from .models import Vente, Dette, PaiementDette, BonusAgent, Agent, DetailDistribution, Client
from .forms import VenteForm, DetteForm, PaiementDetteForm

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

#=========
# #ADMIN
#=========
@login_required
def toutes_les_ventes(request):
    """Voir toutes les ventes (pour administration)"""
    ventes = Vente.objects.select_related(
        'agent', 'client', 'detail_distribution__lot__produit'
    ).order_by('-date_vente')
    
    context = {
        'ventes': ventes,
        'toutes_ventes': True,
    }
    
    return render(request, 'core/ventes/liste_ventes.html', context)

@login_required
def toutes_les_dettes(request):
    """Voir toutes les dettes (pour administration)"""
    dettes = Dette.objects.select_related(
        'vente', 'vente__agent', 'vente__client', 'vente__detail_distribution__lot__produit'
    ).order_by('-date_creation')
    
    # Filtres
    statut = request.GET.get('statut')
    if statut:
        dettes = dettes.filter(statut=statut)
    
    context = {
        'dettes': dettes,
        'statut_actuel': statut,
        'toutes_dettes': True,
    }
    
    return render(request, 'core/ventes/liste_dettes.html', context)

@login_required
def tous_les_bonus(request):
    """Voir tous les bonus (pour administration)"""
    bonus_agents = BonusAgent.objects.select_related('agent').order_by('-total_bonus')
    
    context = {
        'bonus_agents': bonus_agents,
        'tous_bonus': True,
    }
    
    return render(request, 'core/ventes/tous_les_bonus.html', context)

#=====
#FACTURE
#=====

# Liste des factures
def liste_factures(request):
    factures = Facture.objects.all().order_by('-date_depot')
    return render(request, 'core/factures/liste_factures.html', {'factures': factures})

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
#   Statistique et Performance
#=====
