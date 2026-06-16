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
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField,Value
)
from django.db.models.functions import Coalesce

from django import forms
from django.core.exceptions import ValidationError 
from django.utils import timezone
from datetime import datetime, timedelta
# Python stdlib
from datetime import timedelta
from decimal import Decimal
import json

# Project models
from .models import (
    Agent, Client, Vente, Produit,Depense,
    LotEntrepot, DetailDistribution, DistributionAgent,
    Dette, PaiementDette, BonusAgent,Fournisseur,
    JournalModificationDistribution, MouvementStock,
    Recouvrement,VersementBancaire,VersementBancaire,
    RecuVersement,FactureLotEntrepot
)

# Project forms
from .forms import (
    DepenseForm, FactureLotForm, VenteDetailAgentForm,VenteGrosAgentForm,
    VenteSuperviseurForm,DistributionForm, ReceptionLotForm, 
    DetteForm, PaiementDetteForm,RecouvrementForm,TelephoneOrUsernameLoginForm,
    FournisseurForm,VersementForm,FactureLotForm,RecuVersementForm,
    PerteForm,DepenseForm

)

from agents.forms import (
                           
                            SupervisorTerrainAgentCreationForm,
                            
                            DirectionAgentCreationForm,
                            RotSupervisorCreationForm,
                            
                            )


from django.db.models import Sum, Count, Avg, F, Max, Min
from agents.services.agent_stock_service import AgentStockService


from django.core.paginator import Paginator
from urllib.parse import urlencode







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
                    
                    elif agent.type_agent == "rot":
                        return redirect("dashboard_rot")
                    
                    elif agent.type_agent == "gestionnaire_stock":
                        return redirect("dashboard_gestionnaire_stock")
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


@login_required
def access_denied(request, reason=None):
    agent = getattr(request.user, "agent", None)

    context = {
        "agent": agent,
        "reason": reason,
        "redirect_url": None,
        "redirect_label": "Retour",
        "message": "Vous n’avez pas l’autorisation d’accéder à cette page.",
    }

    if agent:
        if agent.est_rot:
            context.update({
                "message": "Cette fonctionnalité est réservée à un autre niveau d’autorisation.",
                "redirect_url": "dashboard_rot",
                "redirect_label": "Aller au tableau de bord ROT",
            })

        elif agent.est_superviseur:
            context.update({
                "message": "Cette action est réservée au Responsable des Opérations (ROT).",
                "redirect_url": "tableau_de_bord_superviseur",
                "redirect_label": "Retour à mon tableau de bord",
            })

        # 🔥 NOUVEAU CAS
        elif agent.est_gestionnaire_stock:
            context.update({
                "message": "Cette fonctionnalité n’est pas accessible depuis votre espace de gestion du stock.",
                "redirect_url": "mise_disposition_rot",  
                "redirect_label": "Retour à la gestion du stock",
            })

        else:
            context.update({
                "redirect_url": "dashboard_agent",
                "redirect_label": "Retour à mon espace",
            })

    return render(request, "core/errors/403.html", context, status=403)
#=========
#AGENT
#========
# views.py





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
    data = []

    fournisseurs = Fournisseur.objects.all().order_by('nom')

    total_valeur_lots = Decimal('0.00')
    total_facture = Decimal('0.00')
    total_reste = Decimal('0.00')

    for f in fournisseurs:
        # =========================
        # LOTS DU FOURNISSEUR
        # =========================
        lots = LotEntrepot.objects.filter(fournisseur=f)

        # -------------------------
        # Produits livrés (liste)
        # -------------------------
        produits = (
            lots
            .values('produit__nom')
            .annotate(
                qte_livree=Coalesce(Sum('quantite_initiale'), Decimal('0.00'))
            )
            .order_by('produit__nom')
        )

        produits_liste = [
            f"{p['produit__nom']} – {p['qte_livree']}"
            for p in produits
        ]

        # -------------------------
        # Valeur des lots reçus
        # -------------------------
        valeur_lots = lots.aggregate(
            total=Coalesce(
                Sum(
                    F('quantite_initiale') * F('prix_achat_unitaire'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                Decimal('0.00')
            )
        )['total']

        # -------------------------
        # Montant facturé (ROT)
        # -------------------------
        montant_facture = FactureLotEntrepot.objects.filter(
            lot__fournisseur=f
        ).aggregate(
            total=Coalesce(
                Sum('montant'),
                Decimal('0.00')
            )
        )['total']

        # -------------------------
        # Reste à facturer (ROT)
        # -------------------------
        reste_a_facturer = max(
            valeur_lots - montant_facture,
            Decimal('0.00')
        )

        data.append({
            'fournisseur': f,
            'contact': getattr(f, 'contact', ""),
            'produits': produits_liste,

            # ROT – FACTURES
            'valeur_lots': valeur_lots,
            'montant_facture': montant_facture,
            'reste_a_facturer': reste_a_facturer,
        })

        # Totaux globaux
        total_valeur_lots += valeur_lots
        total_facture += montant_facture
        total_reste += reste_a_facturer

    return render(
        request,
        'core/fournisseur/liste_fournisseurs.html',
        {
            'fournisseurs': data,
            'total_valeur_lots': total_valeur_lots,
            'total_facture': total_facture,
            'total_reste': total_reste,
        }
    )

@login_required
def detail_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)

    # =========================
    # LOTS DU FOURNISSEUR
    # =========================
    lots_qs = (
        LotEntrepot.objects
        .filter(fournisseur=fournisseur)
        .select_related('produit')
        .prefetch_related('factures')
        .order_by('-date_reception')
    )

    lots = []
    valeur_totale_lots = Decimal('0.00')
    montant_total_facture = Decimal('0.00')

    for lot in lots_qs:
        valeur_lot = lot.quantite_initiale * lot.prix_achat_unitaire

        montant_facture_lot = (
            lot.factures.aggregate(
                total=Coalesce(Sum('montant'), Decimal('0.00'))
            )['total']
        )

        reste_a_facturer_lot = max(
            valeur_lot - montant_facture_lot,
            Decimal('0.00')
        )

        valeur_totale_lots += valeur_lot
        montant_total_facture += montant_facture_lot

        lots.append({
            'lot': lot,
            'reference': lot.reference_lot,
            'date_reception': lot.date_reception,
            'produit': lot.produit.nom,
            'quantite_initiale': lot.quantite_initiale,
            'quantite_restante': lot.quantite_restante,
            'prix_achat': lot.prix_achat_unitaire,

            # ROT – FACTURES
            'valeur_lot': valeur_lot,
            'montant_facture': montant_facture_lot,
            'reste_a_facturer': reste_a_facturer_lot,
            'factures': lot.factures.all(),
        })

    # =========================
    # KPI ROT FOURNISSEUR
    # =========================
    kpi = {
        'valeur_lots': valeur_totale_lots,
        'montant_facture': montant_total_facture,
        'reste_a_facturer': max(
            valeur_totale_lots - montant_total_facture,
            Decimal('0.00')
        ),
        'nb_lots': lots_qs.count(),
        'nb_produits': lots_qs.values('produit').distinct().count(),
        'nb_factures': FactureLotEntrepot.objects.filter(
            lot__fournisseur=fournisseur
        ).count(),
    }

    context = {
        'fournisseur': fournisseur,
        'lots': lots,
        'kpi': kpi,
    }

    return render(
        request,
        'core/fournisseur/detail_fournisseur.html',
        context
    )


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
# views.py
@login_required
def reception_lot(request):
    agent = request.user.agent
    if not agent.est_rot:
        return redirect('access_denied')
    
    if request.method == 'POST':
        form = ReceptionLotForm(request.POST)  
        if form.is_valid():
            try:
                lot = form.save(commit=False)
                lot.receptionne_par = request.user.agent
                lot.save()

                
                # Créer un mouvement de stock
                MouvementStock.objects.create(
                    produit=lot.produit,
                    lot=lot,
                    type_mouvement='RECEPTION',
                    quantite=lot.quantite_initiale,
                    date_mouvement=lot.date_reception
                )
                
                messages.success(request, f"✅ Lot {lot.reference_lot} réceptionné avec succès!")
                
                
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
    lots = (
        LotEntrepot.objects
        .select_related('produit', 'fournisseur')
        .order_by('-date_reception')
    )

    produit_filter = request.GET.get('produit')
    fournisseur_filter = request.GET.get('fournisseur')
    statut_filter = request.GET.get('statut', 'disponible')

    if produit_filter:
        lots = lots.filter(produit__nom__icontains=produit_filter)

    if fournisseur_filter:
        lots = lots.filter(fournisseur__nom__icontains=fournisseur_filter)

    if statut_filter == 'disponible':
        lots = lots.filter(quantite_restante__gt=0)
    elif statut_filter == 'epuise':
        lots = lots.filter(quantite_restante=0)
    
    paginator = Paginator(lots, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    query_params.pop('page', None)

    query_string = urlencode({
        k: v for k, v in query_params.items()
        if v not in [None, '', 'None']
    })
    stats = lots.aggregate(
        total_lots=models.Count('id'),
        total_stock=Coalesce(
            Sum('quantite_restante'),
            Decimal('0.00'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        lots_epuises=models.Count(
            'id',
            filter=models.Q(quantite_restante=0)
        ),
        total_valeur_initiale=Coalesce(
            Sum('valeur_stock_initiale'),
            Decimal('0.00'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        total_valeur_actuelle=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('quantite_restante') * F('prix_achat_unitaire'),
                    output_field=DecimalField(max_digits=14, decimal_places=2)
                )
            ),
            Decimal('0.00'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )

    return render(request, 'core/entrepot/liste_lots.html', {
        'lots': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statut_filter': statut_filter,
        **stats,
    })


@login_required
def detail_lot(request, lot_id):
    lot = get_object_or_404(
        LotEntrepot.objects.select_related('produit', 'fournisseur'),
        id=lot_id
    )



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


    pertes = lot.pertes.all().order_by('-date_perte')
    factures = lot.factures.all().order_by('-date_upload')
    return render(request, 'core/entrepot/detail_lot.html', {
        'lot': lot,
        'factures': factures,
        'perte_form': perte_form,
        'pertes': pertes,
      
        'title': f'Lot {lot.reference_lot}'
    })



@login_required
def mon_stock(request):
    agent = request.user.agent

    if not agent.est_agent_vente:
        return redirect('access_denied')

    service = AgentStockService(agent)
    stock_agent = service.get_stock()

    stock_positif = [p for p in stock_agent if p['quantite_restante'] > 0]
    stock_negatif = [p for p in stock_agent if p['quantite_restante'] < 0]

    distributions_recentes = DistributionAgent.objects.filter(
        agent_terrain=agent,
        date_distribution__gte=timezone.now() - timedelta(days=15)
    ).select_related('superviseur')[:5]

    ventes_recentes = Vente.objects.filter(
        agent=agent,
        date_vente__gte=timezone.now() - timedelta(days=5)
    ).select_related('client', 'detail_distribution__lot__produit')[:5]

    alertes_stock_faible = [
        p for p in stock_positif if p['quantite_restante'] <= 1
    ]

    context = {
        'agent': agent,
        'stock_agent': stock_positif,
        'stock_negatif': stock_negatif,
        'distributions_recentes': distributions_recentes,
        'ventes_recentes': ventes_recentes,
        'alertes_stock_faible': alertes_stock_faible,
        'total_valeur_stock': sum(p['valeur_totale'] for p in stock_positif),
        'total_quantite': sum(p['quantite_restante'] for p in stock_positif),
        'total_produits': len(stock_positif),
        'total_alertes': len(alertes_stock_faible),
    }

    return render(request, 'core/entrepot/mon_stock.html', context)

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
    # -------------------------------
    # Cache user + agent (ANTI N+1)
    # -------------------------------
    user = request.user
    agent = getattr(user, "agent", None)

    # -------------------------------
    # Filtres
    # -------------------------------

    type_filter = request.GET.get('type')
    agent_filter = request.GET.get('agent')
    lot_filter = request.GET.get('lot')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    # -------------------------------
    # QUERYSET OPTIMISÉ (CORRECT)
    # -------------------------------
    distributions = (
        DistributionAgent.objects
        .select_related(
            'superviseur__user',
            'agent_terrain__user'
        )
        .prefetch_related(
            'detaildistribution_set__lot__produit'
        )
        .annotate(
            # Quantité totale distribuée
            quantite_totale_sql=Coalesce(
                Sum('detaildistribution__quantite'),
                0,
                output_field=DecimalField(max_digits=14, decimal_places=2)
            ),

            # Valeur totale au prix GROS
            valeur_gros_sql=Coalesce(
                Sum(
                    F('detaildistribution__quantite') *
                    F('detaildistribution__prix_gros')
                ),
                0,
                output_field=DecimalField(max_digits=14, decimal_places=2)
            ),

            # Valeur totale au prix DÉTAIL
            valeur_detail_sql=Coalesce(
                Sum(
                    F('detaildistribution__quantite') *
                    F('detaildistribution__prix_detail')
                ),
                0,
                output_field=DecimalField(max_digits=14, decimal_places=2)
            ),

            # Coût d’achat total
            valeur_cout_sql=Coalesce(
                Sum(
                    F('detaildistribution__quantite') *
                    F('detaildistribution__lot__prix_achat_unitaire')
                ),
                0,
                output_field=DecimalField(max_digits=14, decimal_places=2)
            ),
        )
        .order_by('-date_distribution')
    )

    # -------------------------------
    # Filtres dynamiques
    # -------------------------------

    if type_filter:
        distributions = distributions.filter(type_distribution=type_filter)

    if agent_filter:
        distributions = distributions.filter(agent_terrain_id=agent_filter)

    if date_debut:
        distributions = distributions.filter(date_distribution__gte=date_debut)

    if date_fin:
        distributions = distributions.filter(date_distribution__lte=date_fin)

    if lot_filter:
        distributions = distributions.filter(
            detaildistribution__lot_id=lot_filter
        ).distinct()

    # -------------------------------
    # TOTAUX GLOBAUX (1 requête SQL)
    # -------------------------------
    totals = distributions.aggregate(
        total_quantite=Sum('quantite_totale_sql'),
        total_valeur_gros=Sum('valeur_gros_sql'),
        total_valeur_detail=Sum('valeur_detail_sql'),
        total_valeur_cout=Sum('valeur_cout_sql'),
    )

    context = {
        'distributions': distributions,

        # KPI
        'total_distributions': distributions.count(),
        'total_quantite': totals['total_quantite'] or 0,
        'total_valeur_gros': totals['total_valeur_gros'] or 0,
        'total_valeur_detail': totals['total_valeur_detail'] or 0,
        'total_valeur_cout': totals['total_valeur_cout'] or 0,

        # Filtres
        'agents_terrain': Agent.objects.filter(
            type_agent__in=['terrain', 'agent_gros']
        ).select_related("user"),

        'lots': LotEntrepot.objects.select_related(
            "produit", "fournisseur"
        ),

        'filter_lot': lot_filter,
        'filter_type': type_filter,
        'filter_agent': agent_filter,
        'date_debut': date_debut,
        'date_fin': date_fin,

    }

    return render(
        request,
        'core/distribution/liste_distributions.html',
        context
    )


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
    """Vue optimisée avec filtres et pagination"""
    try:
        agent = request.user.agent
    except Agent.DoesNotExist:
        return redirect('access_denied')
    
    # Récupérer le paramètre de filtre mensuel
    mois_filtre = request.GET.get('mois')
    annee_filtre = request.GET.get('annee')
    
    # Définir la période par défaut (3 derniers mois)
    date_debut = timezone.now() - timedelta(days=90)
    date_fin = timezone.now()
    
    if mois_filtre and annee_filtre:
        try:
            date_debut = timezone.datetime(int(annee_filtre), int(mois_filtre), 1)
            date_fin = (date_debut + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            date_fin = timezone.make_aware(timezone.datetime.combine(date_fin, timezone.datetime.max.time()))
        except (ValueError, TypeError):
            pass
    
    # Requête optimisée
    distributions = DistributionAgent.objects.filter(
        agent_terrain=agent,
        
        date_distribution__range=[date_debut, date_fin]
    ).select_related('superviseur').prefetch_related(
        'detaildistribution_set__lot__produit'
    ).order_by('-date_distribution')
    
    # Pagination
    paginator = Paginator(distributions, 10)  # 10 distributions par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calcul des statistiques
    total_distributions = distributions.count()
    total_produits = distributions.aggregate(total=Sum('quantite_totale'))['total'] or 0
    
    # Générer les options de mois pour le filtre
    mois_options = []
    current_date = timezone.now()
    for i in range(12):  # 12 derniers mois
        date_option = current_date - timedelta(days=30*i)
        mois_options.append({
            'mois': date_option.month,
            'annee': date_option.year,
            'label': date_option.strftime('%B %Y'),
            'selected': mois_filtre == str(date_option.month) and annee_filtre == str(date_option.year)
        })
    
    context = {
        'agent': agent,
        'page_obj': page_obj,
        'total_distributions': total_distributions,
        'total_produits': total_produits,
        'mois_options': mois_options,
        'mois_filtre': mois_filtre,
        'annee_filtre': annee_filtre,
        'periode_affichee': f"{date_debut.strftime('%d/%m/%Y')} - {date_fin.strftime('%d/%m/%Y')}",
    }
    
    return render(request, 'core/distribution/mes_distributions.html', context)

#=====
#VENTE
#=====
@login_required
def enregistrer_vente(request):
    """
    Vente terrain uniquement :
    - détail
    - comptant
    - prix imposé
    """

    try:
        agent = request.user.agent
    except Agent.DoesNotExist:
        messages.error(request, "Profil agent introuvable.")
        return redirect('login')
    
    if agent.est_agent_terrain:
        FormClass = VenteDetailAgentForm

    elif agent.est_agent_gros:
        FormClass = VenteGrosAgentForm

    elif agent.est_superviseur:
        FormClass = VenteSuperviseurForm
        
    else:
        return redirect('access_denied')

    form = FormClass(request.POST or None, agent=agent)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "✅ Vente enregistrée avec succès")
        return redirect('liste_ventes')
    
    return render(request, 'core/ventes/enregistrer_vente.html', {
        'form': form,
        'agent': agent
    })


@login_required
def liste_ventes(request):
    """Lister les ventes de l'agent (version simplifiée)"""
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('login')
    
    # Récupérer les ventes récentes (3 derniers mois)
    trois_mois = timezone.now() - timedelta(days=90)
    ventes = Vente.objects.filter(
        agent=agent,
        est_supprime=False,
        date_vente__gte=trois_mois
    ).select_related(
        'client', 
        'detail_distribution__lot__produit'
    ).order_by('-date_vente')
    
    # Pagination
    paginator = Paginator(ventes, 15)  # 15 ventes par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques basiques
    total_ventes = ventes.count()
    ventes_comptant = ventes.filter(mode_paiement='comptant').count()
    ventes_credit = ventes.filter(mode_paiement='credit').count()
    
    # Calcul du chiffre d'affaires total
    chiffre_affaires_total = sum(vente.total_vente for vente in ventes)
    
    context = {
        'page_obj': page_obj,
        'total_ventes': total_ventes,
        'chiffre_affaires_total': chiffre_affaires_total,
        'ventes_comptant': ventes_comptant,
        'ventes_credit': ventes_credit,
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
                    
                   
                    messages.success(request, 
                        f"Paiement enregistré ! Montant: {paiement.montant} FCFA - "
                        f"Reste à payer: {dette.montant_restant} FCFA."
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
    
    # Filtres temporels
    periode = request.GET.get('periode', 'mois_courant')  # mois_courant, 30j, 90j
    maintenant = timezone.now()
    
    if periode == '30j':
        date_debut = maintenant - timedelta(days=30)
    elif periode == '90j':
        date_debut = maintenant - timedelta(days=90)
    else:  # mois_courant par défaut
        date_debut = maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Récupérer les recouvrements avec bonus dans la période
    recouvrements_bonus = Recouvrement.objects.filter(
        agent=agent,
        bonus_accorde=True,
        date_recouvrement__gte=date_debut
    ).select_related('vente', 'vente__client', 'vente__detail_distribution__lot__produit')
    
    # Calcul des statistiques
    produits_recouverts = recouvrements_bonus.aggregate(
        total_produits=Sum('vente__quantite')
    )['total_produits'] or 0
    
    bonus_periode = produits_recouverts * 100
    
    # Statistiques détaillées
    stats_recouvrements = recouvrements_bonus.aggregate(
        total_montant=Sum('montant_recouvre'),
        total_bonus=Sum('montant_bonus'),
        nombre_recouvrements=Count('id')
    )
    
    context = {
        'bonus_agent': bonus_agent,
        'recouvrements_bonus': recouvrements_bonus,
        'produits_recouverts': produits_recouverts,
        'bonus_periode': bonus_periode,
        'periode_actuelle': periode,
        'date_debut': date_debut,
        'stats_recouvrements': stats_recouvrements,
    }
    
    return render(request, 'core/ventes/consulter_bonus.html', context)

@login_required
def liste_dettes(request):
    try:
        agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        messages.error(request, "Aucun agent trouvé.")
        return redirect('dashboard')
    
    # Récupérer les dettes (6 derniers mois)
    six_mois = timezone.now() - timedelta(days=180)
    dettes = Dette.objects.filter(
        vente__agent=agent,
        date_creation__gte=six_mois
    ).select_related(
        'vente__client',
        'vente__detail_distribution__lot__produit'
    ).order_by('-date_creation')
    
    # Filtres simples
    statut = request.GET.get('statut')
    if statut:
        dettes = dettes.filter(statut=statut)
    
    # Pagination
    paginator = Paginator(dettes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calcul des totaux uniquement pour les dettes actives
    dettes_actives = dettes.exclude(statut="paye")
    total_restant = dettes_actives.aggregate(
        total=models.Sum("montant_restant")
    )["total"] or 0
    
    # Compteurs basiques
    total_dettes = dettes.count()
    dettes_actives_count = dettes_actives.count()

    context = {
        'page_obj': page_obj,
        'statut_actuel': statut,
        'total_dettes': total_dettes,
        'dettes_actives_count': dettes_actives_count,
        'total_restant': total_restant,
    }
    
    return render(request, 'core/ventes/liste_dettes.html', context)

@login_required
def get_info_distribution(request, detail_id):
    try:
        detail = DetailDistribution.objects.get(id=detail_id)

        # Calcul dynamique correct
        quantite_restante = detail.quantite_restante_calculee

        data = {
            'produit': detail.lot.produit.nom,
            'quantite_disponible': float(quantite_restante),
            'prix_gros': float(detail.prix_gros) if detail.prix_gros else None,
            'prix_detail': float(detail.prix_detail) if detail.prix_detail else None,
            'specification': detail.specification or '',
            'reference_lot': detail.lot.reference_lot or f"Lot#{detail.lot.id}",
        }

        return JsonResponse(data)

    except DetailDistribution.DoesNotExist:
        return JsonResponse({'error': 'Détail introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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





@login_required
def gestion_factures_lot(request, lot_id):
    lot = get_object_or_404(LotEntrepot, id=lot_id)
    factures = lot.factures.all().order_by('-date_upload')
    
    # Message contextuel si c'est une nouvelle création
    is_new_lot = request.GET.get('nouveau', False)
    if is_new_lot and not factures.exists():
        messages.info(request, 
            "✅ Lot créé avec succès ! Vous pouvez maintenant ajouter des factures.",
            extra_tags='info')
    
    # Calcul des montants
    montant_total_lot = lot.montant_total
    montant_total_factures = lot.total_facture_lot
    reste_a_payer = max(montant_total_lot - montant_total_factures, Decimal('0'))
    
    if request.method == 'POST':
        form = FactureLotForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                factures_crees = form.save(lot=lot, user=request.user, rot=request.user.agent)
                count = len(factures_crees)
                
                # Message de succès
                messages.success(request, 
                    f"✅ {count} facture(s) ajoutée(s) avec succès !",
                    extra_tags='success')
                
                # Rediriger si demandé
                if 'redirect_to_detail' in request.POST:
                    return redirect('detail_lot', lot_id=lot.id)
                else:
                    # Recharger la page pour voir les nouvelles factures
                    return redirect('gestion_factures_lot', lot_id=lot.id)
                    
            except Exception as e:
                messages.error(request, 
                    f"❌ Erreur lors de l'enregistrement des factures : {str(e)}",
                    extra_tags='danger')
        else:
            # Afficher les erreurs spécifiques
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {field}: {error}", extra_tags='danger')
    
    else:
        form = FactureLotForm()
    
    context = {
        'lot': lot,
        'factures': factures,
        'form': form,
        'montant_total_lot': montant_total_lot,
        'montant_total_factures': montant_total_factures,
        'reste_a_payer': reste_a_payer,
        'est_solde': lot.est_solde,
        'pourcentage_paye': (montant_total_factures / montant_total_lot * 100) if montant_total_lot > 0 else 0,
    }
    
    return render(request, 'core/factures/gestion_factures_lot.html', context)


@login_required
def creer_versement(request):
    agent_connecte = request.user.agent

    if not agent_connecte.est_rot:
        return redirect("access_denied")

    if request.method == "POST":
        form = VersementForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(rot=agent_connecte)
            messages.success(request, "✅ Versement enregistré par le ROT")
            return redirect("liste_versement")
    else:
        form = VersementForm()

    return render(
        request,
        "core/factures/creer_versement.html",
        {
            "form": form,
            "rot": agent_connecte
        }
    )


@login_required
def modifier_versement(request, versement_id):
    versement = get_object_or_404(VersementBancaire, id=versement_id)

    if not hasattr(request.user, 'agent'):
        messages.error(request, "Accès réservé aux agents.")
        return redirect("login")

    agent = request.user.agent

    # 🔐 Permissions
    if agent.est_rot:
        if versement.effectue_par != agent:
            messages.error(request, "Vous ne pouvez modifier que vos propres versements.")
            return redirect("liste_versement")

    elif not agent.est_direction:
        messages.error(request, "Accès non autorisé.")
        return redirect("liste_versement")

    if request.method == "POST":
        form = VersementForm(request.POST, request.FILES, instance=versement)
        if form.is_valid():
            form.save(rot=versement.effectue_par)
            messages.success(request, "✅ Versement modifié avec succès.")
            return redirect("detail_versement", versement_id=versement.id)
    else:
        form = VersementForm(instance=versement)

    return render(
        request,
        "core/factures/modifier_versement.html",
        {
            "form": form,
            "versement": versement,
        }
    )



@login_required
def liste_versement(request):
    versements = (
        VersementBancaire.objects
        .all()
        .order_by('-date_versement_reelle')
    )

    total_vente = versements.aggregate(
        total=Sum('montant_vente')
    )['total'] or 0

    total_hors_vente = versements.aggregate(
        total=Sum('montant_hors_vente')
    )['total'] or 0

    total_general = total_vente + total_hors_vente

    total_depenses = (
        Depense.objects
        .aggregate(total=Sum('montant'))['total'] or 0
    )
    # =========================
    # PAGINATION
    # =========================
    paginator = Paginator(versements, 10)
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

    context = {
        'versements': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,

        'total_vente': total_vente,
        'total_hors_vente': total_hors_vente,
        'total_depenses': total_depenses,
        'total_general': total_general,
    }

    return render(
        request,
        'core/factures/liste_versement.html',
        context
    )

@login_required
def detail_versement(request, versement_id):
    versement = get_object_or_404(VersementBancaire, id=versement_id)

    depenses = versement.depenses.all()
    total_depenses = versement.total_depenses_associees

    # ✅ LOGIQUE SAINE
    cash_vente_restant = versement.montant_vente - total_depenses

    context = {
        'versement': versement,
        'depenses': depenses,
        'total_depenses': total_depenses,
        'cash_vente_restant': cash_vente_restant,
    }

    return render(request, 'core/factures/detail_versement.html', context)


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
    lots_avec_facture = LotEntrepot.objects.all().order_by('-date_reception')
    
    context = {
        'lots_avec_facture': lots_avec_facture,
        'title': 'Factures Entrepôt'
    }
    return render(request, 'core/factures/liste_factures_entrepot.html', context)
#
#   DEPENSES
#
from django.utils.dateparse import parse_date

from datetime import date
from django.utils.dateparse import parse_date

from datetime import date
from django.utils.dateparse import parse_date

@login_required
def liste_depenses(request):
    agent = request.user.agent

    depenses = Depense.objects.all().order_by('-date_depense')

    categorie = request.GET.get('categorie')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    show_all = request.GET.get('all')  # 👈 NOUVEAU

    today = date.today()

    # 📌 Mois en cours PAR DÉFAUT (uniquement si rien n’est demandé)
    if not show_all and not date_debut and not date_fin:
        depenses = depenses.filter(
            date_depense__year=today.year,
            date_depense__month=today.month
            
        )
        date_debut = today.replace(day=1).isoformat()
        date_fin = today.isoformat()

    # Filtres manuels
    if categorie:
        depenses = depenses.filter(categorie=categorie)

    if date_debut:
        depenses = depenses.filter(
            date_depense__gte=parse_date(date_debut)
        )

    if date_fin:
        depenses = depenses.filter(
            date_depense__lte=parse_date(date_fin)
        )

    return render(request, 'core/depenses/liste.html', {
        'depenses': depenses,
        'categories': Depense._meta.get_field('categorie').choices,
        'categorie_active': categorie,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'show_all': show_all,
    })


@login_required
def detail_depense(request, depense_id):
    depense = get_object_or_404(Depense, id=depense_id)
    agent = request.user.agent

    # ✅ Permission : uniquement ROT ou Direction
    if not (agent.est_rot or agent.est_direction):
        return redirect('access_denied')

    return render(request, 'core/depenses/detail.html', {
        'depense': depense
    })

    
@login_required
def creer_depense(request):
    agent = request.user.agent

    if not agent.est_rot:
        return redirect('access_denied')

    if request.method == 'POST':
        form = DepenseForm(request.POST)
        if form.is_valid():
            form.save(agent=agent)
            messages.success(request, "✅ Dépense enregistrée")
            return redirect('liste_depenses')
    else:
        form = DepenseForm()

    return render(request, 'core/depenses/form.html', {
        'form': form,
        'titre': "Nouvelle dépense"
    })


@login_required
def modifier_depense(request, depense_id):
    depense = get_object_or_404(Depense, id=depense_id)
    agent = request.user.agent

    if agent != depense.effectue_par and not agent.est_direction:
        return redirect('access_denied')

    if request.method == 'POST':
        form = DepenseForm(request.POST, instance=depense)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Dépense modifiée")
            return redirect('liste_depenses')
    else:
        form = DepenseForm(instance=depense)

    return render(request, 'core/depenses/form.html', {
        'form': form,
        'titre': "Modifier la dépense"
    })




#=========
# #RECOUVREMENT
#=========

@login_required
def creer_recouvrement(request, agent_id):

    agent_connecte = (
        Agent.objects
        .select_related('user')
        .get(user=request.user)
    )

    agent_cible = get_object_or_404(
        Agent.objects.select_related('user'),
        id=agent_id
    )

    # =========================
    # SÉCURITÉ – RÔLES
    # =========================

    # ❌ Un agent terrain ne peut jamais recouvrer
    if agent_connecte.est_agent_terrain:
        return redirect('access_denied')

    # ❌ Seul un superviseur peut accéder
    if not agent_connecte.est_superviseur:
        return redirect('access_denied')

    # =========================
    # SÉCURITÉ – PÉRIMÈTRE
    # =========================

    # ✅ Auto-recouvrement
    if agent_cible.id == agent_connecte.id:
        autorise = True

    # ✅ Recouvrement d’un agent sous ce superviseur (terrain OU gros)
    elif agent_cible.superviseur_id == agent_connecte.id:
        autorise = True

    # ❌ Tout le reste
    else:
        autorise = False

    if not autorise:
        return redirect('access_denied')

    # =========================
    # FORMULAIRE
    # =========================

    if request.method == 'POST':
        form = RecouvrementForm(request.POST, agent=agent_cible)
        if form.is_valid():
            recouvrement = form.save(commit=False)
            recouvrement.agent = agent_cible
            recouvrement.superviseur = agent_connecte
            recouvrement.save()

            if agent_cible.id == agent_connecte.id:
                messages.success(
                    request,
                    f"✅ Auto-recouvrement de {recouvrement.montant_recouvre} FCFA effectué avec succès."
                )
            else:
                messages.success(
                    request,
                    f"✅ Recouvrement de {recouvrement.montant_recouvre} FCFA effectué auprès de {agent_cible.full_name}."
                )

            return redirect('liste_agents_recouvrement')
    else:
        form = RecouvrementForm(agent=agent_cible)

    # =========================
    # CONTEXTE
    # =========================

    context = {
        'agent': agent_cible,
        'form': form,
        'argent_en_possession': agent_cible.argent_en_possession,
        'total_ventes': agent_cible.total_ventes,
        'total_recouvre': agent_cible.total_recouvre,
        'est_auto_recouvrement': agent_cible.id == agent_connecte.id,
    }

    return render(
        request,
        'core/recouvrement/creer_recouvrement.html',
        context
    )

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
    agent_connecte = (
        Agent.objects
        .select_related("user")
        .get(user=request.user)
    )

    # =========================
    # SÉCURITÉ : QUI VOIT QUOI
    # =========================

    if agent_connecte.est_superviseur:
        agents_qs = Agent.objects.filter(
            type_agent__in=["terrain", "agent_gros"],
            est_actif=True,
            superviseur=agent_connecte
        ).select_related("user")


    else:
        # Terrain / autre → interdit
        return redirect("access_denied")

    # =========================
    # FILTRE MENSUEL
    # =========================
    
    mois_str = request.GET.get("mois")  # ex: "2026-01"
    
    now = timezone.now()
    
    if mois_str:
        try:
            date_debut = datetime.strptime(mois_str, "%Y-%m").replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            date_debut = timezone.make_aware(date_debut)
        except ValueError:
            date_debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        date_debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # fin de période = maintenant si mois courant, sinon fin du mois
    if date_debut.month == now.month and date_debut.year == now.year:
        date_fin = now
    else:
        if date_debut.month == 12:
            date_fin = date_debut.replace(year=date_debut.year + 1, month=1)
        else:
            date_fin = date_debut.replace(month=date_debut.month + 1)
    

    agents_ids = list(agents_qs.values_list("id", flat=True))

    # =========================
    # AGRÉGATIONS SQL
    # =========================

    ventes_par_agent = dict(
        Vente.objects
        .filter(
            agent_id__in=agents_ids,
            date_vente__gte=date_debut,
            date_vente__lt=date_fin
        )
        .values("agent_id")
        .annotate(
            total=models.Sum(
                models.F("quantite") * models.F("prix_vente_unitaire")
            )
        )
        .values_list("agent_id", "total")
    )

    recouvrements_par_agent = dict(
        Recouvrement.objects
        .filter(
                agent_id__in=agents_ids,
                date_recouvrement__gte=date_debut,
                date_recouvrement__lt=date_fin
                )
        .values("agent_id")
        .annotate(total=models.Sum("montant_recouvre"))
        .values_list("agent_id", "total")
    )


    # =========================
    # ASSEMBLAGE
    # =========================

    agents_data = []
    total_ventes_tous_agents = Decimal("0.00")
    total_recouvre_tous_agents = Decimal("0.00")

    for agent in agents_qs:
        total_ventes = ventes_par_agent.get(agent.id, Decimal("0.00")) or Decimal("0.00")
        total_recouvre = recouvrements_par_agent.get(agent.id, Decimal("0.00")) or Decimal("0.00")
       
        difference = max(total_ventes - total_recouvre, Decimal("0.00"))


        if difference == 0:
            statut = "OK"
            couleur = "success"
        else:
            statut = f"{difference:,.0f} FCFA"
            couleur = "warning"


        total_ventes_tous_agents += total_ventes
        total_recouvre_tous_agents += total_recouvre

        agents_data.append({
            "agent": agent,
            "total_ventes": total_ventes,
            "total_recouvre": total_recouvre,
           
            "difference": difference,
            "statut": statut,
            "couleur": couleur,
         
        })

    context = {
        "agents_data": agents_data,
        "total_ventes_tous_agents": total_ventes_tous_agents,
        "total_recouvre_tous_agents": total_recouvre_tous_agents,
        "reste_a_recouvrir": total_ventes_tous_agents - total_recouvre_tous_agents,
        "agent_connecte": agent_connecte,
        "mois_selectionne": date_debut.strftime("%Y-%m"),
    }

    return render(
        request,
        "core/recouvrement/liste_agents.html",
        context
    )


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
        superviseur = Agent.objects.get(user=request.user,  type_agent__in=['entrepot', 'rot'])
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
    agents_terrain = Agent.objects.filter(type_agent__in=['terrain', 'agent_gros']).select_related('user')
    
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
    agent = get_object_or_404(Agent, id=agent_id, type_agent__in=['terrain', 'agent_gros'])
    
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
    agents_list = Agent.objects.filter(type_agent__in=['terrain', 'agent_gros'])
    
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
