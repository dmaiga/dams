from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse

from core.models import LotEntrepot, AffectationLotSuperviseur, MouvementStock, Agent, Produit, Fournisseur
from core.forms import ReceptionLotForm
from .forms import AffectationSuperviseurForm, TYPES_AGENT_TERRAIN


def _acces_stock(agent):
    return agent.est_gestionnaire_stock or agent.est_rot


@login_required
def liste_lots(request):
    agent = request.user.agent
    if not _acces_stock(agent):
        return redirect('access_denied')

    lots_qs = (
        LotEntrepot.objects
        .select_related('produit', 'fournisseur', 'receptionne_par__user')
        .order_by('-date_reception')
    )

    produit_id = request.GET.get('produit')
    fournisseur_id = request.GET.get('fournisseur')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    if produit_id:
        lots_qs = lots_qs.filter(produit_id=produit_id)
    if fournisseur_id:
        lots_qs = lots_qs.filter(fournisseur_id=fournisseur_id)
    if date_debut:
        lots_qs = lots_qs.filter(date_reception__gte=date_debut)
    if date_fin:
        lots_qs = lots_qs.filter(date_reception__lte=date_fin)

    paginator = Paginator(lots_qs, 30)
    lots = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'marchandise/liste_lots.html', {
        'lots': lots,
        'produits': Produit.objects.order_by('nom'),
        'fournisseurs': Fournisseur.objects.order_by('nom'),
        'filtre_produit': produit_id or '',
        'filtre_fournisseur': fournisseur_id or '',
        'filtre_date_debut': date_debut or '',
        'filtre_date_fin': date_fin or '',
    })


@login_required
def detail_lot(request, pk):
    agent = request.user.agent
    if not _acces_stock(agent):
        return redirect('access_denied')

    lot = get_object_or_404(
        LotEntrepot.objects.select_related('produit', 'fournisseur', 'receptionne_par__user'),
        pk=pk
    )
    affectations = (
        AffectationLotSuperviseur.objects
        .filter(lot=lot)
        .select_related('superviseur__user', 'attribue_par__user', 'agent_terrain_direct__user')
        .order_by('-date_affectation')
    )
    mouvements = (
        MouvementStock.objects
        .filter(lot=lot)
        .order_by('-date_mouvement')
    )
    return render(request, 'marchandise/detail_lot.html', {
        'lot': lot,
        'affectations': affectations,
        'mouvements': mouvements,
    })


@login_required
def reception_lot(request):
    agent = request.user.agent
    if not _acces_stock(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = ReceptionLotForm(request.POST)
        if form.is_valid():
            try:
                lot = form.save(commit=False)
                lot.receptionne_par = agent
                lot.save()
                MouvementStock.objects.create(
                    produit=lot.produit,
                    lot=lot,
                    type_mouvement='RECEPTION',
                    quantite=lot.quantite_initiale,
                    date_mouvement=lot.date_reception
                )
                messages.success(request, f"Lot {lot.reference_lot} réceptionné avec succès.")
                return redirect('marchandise:liste_lots')
            except Exception as e:
                messages.error(request, f"Erreur lors de l'enregistrement : {e}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ReceptionLotForm()

    return render(request, 'marchandise/reception_lot.html', {'form': form})


@login_required
def affecter_superviseur(request):
    agent = request.user.agent
    if not _acces_stock(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = AffectationSuperviseurForm(request.POST)
        if form.is_valid():
            try:
                affectation = form.save(agent)
                messages.success(
                    request,
                    f"{affectation.quantite_initiale} unité(s) de "
                    f"{affectation.lot.produit.nom} affectée(s) à "
                    f"{affectation.superviseur.full_name}."
                )
                return redirect('marchandise:historique_affectations')
            except Exception as e:
                messages.error(request, f"Erreur : {e}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AffectationSuperviseurForm()

    return render(request, 'marchandise/affecter_superviseur.html', {'form': form})


@login_required
def ajax_agents_par_superviseur(request):
    superviseur_id = request.GET.get('superviseur_id')

    agents = Agent.objects.filter(
        superviseur_id=superviseur_id,
        type_agent__in=TYPES_AGENT_TERRAIN,
        est_actif=True
    ).select_related('user').order_by('user__last_name')

    data = [
        {'id': a.id, 'label': a.full_name}
        for a in agents
    ]
    return JsonResponse(data, safe=False)


@login_required
def historique_affectations(request):
    agent = request.user.agent
    if not _acces_stock(agent):
        return redirect('access_denied')

    affectations_qs = (
        AffectationLotSuperviseur.objects
        .select_related(
            'lot__produit', 'lot__fournisseur',
            'superviseur__user', 'attribue_par__user', 'agent_terrain_direct__user'
        )
        .order_by('-date_affectation')
    )

    produit_id = request.GET.get('produit')
    superviseur_id = request.GET.get('superviseur')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    if produit_id:
        affectations_qs = affectations_qs.filter(lot__produit_id=produit_id)
    if superviseur_id:
        affectations_qs = affectations_qs.filter(superviseur_id=superviseur_id)
    if date_debut:
        affectations_qs = affectations_qs.filter(date_affectation__gte=date_debut)
    if date_fin:
        affectations_qs = affectations_qs.filter(date_affectation__lte=date_fin)

    paginator = Paginator(affectations_qs, 30)
    affectations = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'marchandise/historique_affectations.html', {
        'affectations': affectations,
        'produits': Produit.objects.order_by('nom'),
        'superviseurs': Agent.objects.filter(type_agent='entrepot').order_by('user__first_name'),
        'filtre_produit': produit_id or '',
        'filtre_superviseur': superviseur_id or '',
        'filtre_date_debut': date_debut or '',
        'filtre_date_fin': date_fin or '',
    })
