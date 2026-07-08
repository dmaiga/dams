from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse

from core.models import AffectationLotSuperviseur, DetailDistribution, Vente, Recouvrement
from .forms import DistributionForm, VenteForm


def _acces_superviseur(agent):
    return agent.est_superviseur


@login_required
def liste_affectations(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    affectations = (
        AffectationLotSuperviseur.objects
        .filter(superviseur=agent, agent_terrain_direct__isnull=True, quantite_restante__gt=0)
        .select_related('lot__produit', 'lot__fournisseur')
        .order_by('-date_affectation')
    )
    return render(request, 'vente/liste_affectations.html', {'affectations': affectations})


@login_required
def creer_distribution(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = DistributionForm(request.POST, superviseur=agent)
        if form.is_valid():
            try:
                distribution = form.save(superviseur=agent)
                messages.success(request, "Distribution enregistrée.")
                return redirect('vente:detail_distribution', pk=distribution.pk)
            except Exception as e:
                messages.error(request, f"Erreur : {e}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = DistributionForm(superviseur=agent)

    return render(request, 'vente/creer_distribution.html', {'form': form})


@login_required
def detail_distribution_superviseur(request, pk):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    details = (
        DetailDistribution.objects
        .filter(distribution__pk=pk, distribution__superviseur=agent)
        .select_related('distribution__agent_terrain__user', 'lot__produit')
    )
    if not details.exists():
        messages.error(request, "Distribution introuvable.")
        return redirect('vente:liste_affectations')

    ventes = (
        Vente.objects
        .filter(detail_distribution__in=details, est_supprime=False)
        .select_related('detail_distribution__lot__produit')
        .order_by('-date_vente')
    )

    return render(request, 'vente/detail_distribution_superviseur.html', {
        'details': details,
        'ventes': ventes,
        'distribution_pk': pk,
    })


@login_required
def enregistrer_vente(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = VenteForm(request.POST, superviseur=agent)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Toutes les ventes sont enregistrées au comptant pour l'instant :
                    # le recouvrement est donc systématiquement créé, sans dette.
                    vente = form.save()
                    Recouvrement.objects.create(
                        agent=vente.agent,
                        superviseur=agent,
                        vente=vente,
                        montant_recouvre=vente.total_vente,
                        date_recouvrement=vente.date_vente,
                    )
                messages.success(
                    request,
                    f"Vente de {vente.quantite} enregistrée — recouvrement créé automatiquement."
                )
                return redirect('vente:historique_ventes')
            except Exception as e:
                messages.error(request, f"Erreur : {e}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = VenteForm(superviseur=agent)

    return render(request, 'vente/enregistrer_vente.html', {'form': form})


@login_required
def historique_ventes(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    ventes_qs = (
        Vente.objects
        .filter(detail_distribution__distribution__superviseur=agent, est_supprime=False)
        .select_related('agent__user', 'detail_distribution__lot__produit', 'dette')
        .order_by('-date_vente')
    )
    paginator = Paginator(ventes_qs, 30)
    ventes = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'vente/historique_ventes.html', {'ventes': ventes})


# =========================================================
# AJAX
# =========================================================

@login_required
def ajax_affectations_par_agent(request):
    """Alimente le sélecteur 'affectation' de DistributionForm : cas d'exception uniquement."""
    superviseur = request.user.agent
    affectations = (
        AffectationLotSuperviseur.objects
        .filter(superviseur=superviseur, agent_terrain_direct__isnull=True, quantite_restante__gt=0)
        .select_related('lot__produit', 'lot__fournisseur')
        .order_by('-date_affectation')
    )
    data = [
        {
            'id': a.id,
            'label': f"{a.lot.produit.nom} | Reçu {a.date_affectation:%d/%m/%Y} | Restant : {a.quantite_restante}",
        }
        for a in affectations
    ]
    return JsonResponse(data, safe=False)


@login_required
def ajax_distributions_par_agent(request):
    """Alimente le sélecteur 'detail_distribution' de VenteForm."""
    agent_id = request.GET.get('agent_id')
    superviseur = request.user.agent

    details = (
        DetailDistribution.objects
        .filter(distribution__superviseur=superviseur, distribution__agent_terrain_id=agent_id)
        .select_related('lot__produit')
    )

    data = [
        {
            'id': d.id,
            'label': f"{d.lot.produit.nom} | reste {d.quantite_restante_calculee}",
            'type_vente_suggere': (
                d.distribution.agent_terrain.type_vente_par_defaut()
                if d.distribution.agent_terrain_id != superviseur.id else None
            ),
        }
        for d in details
        if d.quantite_restante_calculee > 0
    ]
    return JsonResponse(data, safe=False)
