from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
from django.http import JsonResponse

from core.models import (
    Agent, AffectationLotSuperviseur, CorrectionAdministrative, DetailDistribution,
    Fournisseur, Produit, Vente, Recouvrement,
)
from core.services.corrections import est_correcteur_ventes
from vente.forms import CorrectionVenteGroupeForm, DistributionForm, VenteForm
from vente.services import (
    ANOMALIES_PRIX, CorrectionVenteService, classer_prix, details_avec_restant,
    lister_ventes_a_surveiller,
)


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

    details = details_avec_restant(
        DetailDistribution.objects
        .filter(distribution__superviseur=superviseur, distribution__agent_terrain_id=agent_id)
        .select_related('lot__produit', 'distribution')
    ).filter(restant__gt=0)

    # Même agent pour toutes les lignes : une seule lecture au lieu d'une par détail
    agent_cible = Agent.objects.filter(pk=agent_id).first()
    type_suggere = (
        agent_cible.type_vente_par_defaut()
        if agent_cible and agent_cible.pk != superviseur.pk else None
    )

    data = [
        {
            'id': d.id,
            'label': f"{d.lot.produit.nom} | Affecté le {d.distribution.date_distribution:%d/%m/%Y} | reste {d.restant}",
            'type_vente_suggere': type_suggere,
            # Perte déclarable uniquement pour un produit vrac (non conditionné) — cf. PerteDistributionForm.
            'is_vrac': d.lot.produit.poids_unitaire_kg is None,
        }
        for d in details
    ]
    return JsonResponse(data, safe=False)


# ----------------------------------------------------------------------------
# SURVEILLANCE / CORRECTION DES VENTES — groupe « Correcteurs ventes »
# ----------------------------------------------------------------------------
#
# Pages dédiées (gabarit superviseur, aucune donnée CA/marge) : le groupe
# n'accède pas aux écrans d'analyse de la direction. Elles appellent le même
# CorrectionVenteService que l'écran direction (audit CorrectionAdministrative,
# stock de l'agent et recouvrement recalculés).

TYPES_CORRECTION_VENTE = ('VENTE_PRIX_QUANTITE', 'VENTE_DATE')


def _resoudre_periode(get):
    """Période de la liste : `hebdo` (7 derniers jours, défaut), `mensuel`
    (mois en cours) ou `custom` (`debut`/`fin`)."""
    aujourdhui = timezone.localdate()
    periode = get.get('periode') or 'hebdo'
    if periode == 'mensuel':
        return periode, aujourdhui.replace(day=1), aujourdhui
    if periode == 'custom':
        debut = parse_date(get.get('debut') or '')
        fin = parse_date(get.get('fin') or '')
        return periode, debut, fin
    return 'hebdo', aujourdhui - timedelta(days=6), aujourdhui


JOURS_PAR_PAGE = 7


@login_required
@user_passes_test(est_correcteur_ventes)
def corrections_ventes(request):
    get = request.GET
    agent_id = get.get('agent') or ''
    superviseur_id = get.get('superviseur') or ''
    produit_id = get.get('produit') or ''
    fournisseur_id = get.get('fournisseur') or ''
    anomalie = get.get('anomalie') or ''
    periode, debut, fin = _resoudre_periode(get)

    ventes = lister_ventes_a_surveiller(
        agent_id=agent_id or None,
        superviseur_id=superviseur_id or None,
        produit_id=produit_id or None,
        fournisseur_id=fournisseur_id or None,
        anomalie=anomalie,
        debut=debut,
        fin=fin,
    )

    # Pagination par JOURS (pas par lignes) : une journée n'est jamais coupée.
    jours = list(ventes.dates('date_vente', 'day', order='DESC'))
    page_obj = Paginator(jours, JOURS_PAR_PAGE).get_page(get.get('page'))
    jours_page = list(page_obj.object_list)

    ventes_page = list(
        ventes.filter(date_vente__date__in=jours_page).order_by(
            'detail_distribution__distribution__superviseur__user__first_name',
            'detail_distribution__distribution__superviseur_id',
            '-date_vente',
        )
    )
    ids_corriges = set(
        CorrectionAdministrative.objects.filter(
            content_type=ContentType.objects.get_for_model(Vente),
            object_id__in=[v.id for v in ventes_page],
            type_correction__in=TYPES_CORRECTION_VENTE,
        ).values_list('object_id', flat=True)
    )

    # jour (récent d'abord) → superviseur → ventes : un superviseur est terminé
    # avant d'afficher le suivant, et un jour avant le jour précédent.
    par_jour = {jour: [] for jour in jours_page}
    for vente in ventes_page:
        vente.deja_corrigee = vente.id in ids_corriges
        vente.alerte_prix = classer_prix(
            vente.prix_vente_unitaire, vente.detail_distribution.lot.prix_achat_unitaire
        )
        jour = timezone.localtime(vente.date_vente).date()
        superviseur = vente.detail_distribution.distribution.superviseur
        groupes = par_jour[jour]
        if not groupes or groupes[-1]['superviseur'] != superviseur:
            groupes.append({'superviseur': superviseur, 'ventes': []})
        groupes[-1]['ventes'].append(vente)
    journees = [{'jour': jour, 'groupes': par_jour[jour]} for jour in jours_page]

    return render(request, 'vente/corrections/liste.html', {
        'page_obj': page_obj,
        'journees': journees,
        'agents': Agent.objects.filter(
            type_agent__in=('terrain', 'agent_gros', 'agent_polivalent', 'stagiaire')
        ).select_related('user').order_by('user__first_name', 'user__username'),
        'superviseurs': Agent.objects.filter(type_agent='entrepot')
            .select_related('user').order_by('user__first_name', 'user__username'),
        'produits': Produit.objects.order_by('nom'),
        'fournisseurs': Fournisseur.objects.order_by('nom'),
        'agent_id': agent_id,
        'superviseur_id': superviseur_id,
        'produit_id': produit_id,
        'fournisseur_id': fournisseur_id,
        'anomalie': anomalie,
        'anomalies': ANOMALIES_PRIX,
        'periode': periode,
        'debut': debut.isoformat() if debut else '',
        'fin': fin.isoformat() if fin else '',
    })


@login_required
@user_passes_test(est_correcteur_ventes)
def corriger_vente_groupe(request, vente_id):
    vente = get_object_or_404(
        Vente.objects.select_related(
            'agent__user',
            'detail_distribution__lot__produit',
            'detail_distribution__lot__fournisseur',
            'detail_distribution__distribution__superviseur__user',
        ),
        pk=vente_id, est_supprime=False,
    )

    if request.method == 'POST':
        form = CorrectionVenteGroupeForm(request.POST)
        if form.is_valid():
            kwargs = {'motif': form.cleaned_data['motif'], 'utilisateur': request.user}
            for champ in ('prix_vente_unitaire', 'quantite'):
                if form.cleaned_data.get(champ) is not None:
                    kwargs[champ] = form.cleaned_data[champ]
            try:
                CorrectionVenteService.corriger_vente(vente.id, **kwargs)
            except ValidationError as exc:
                for erreur in getattr(exc, 'messages', [str(exc)]):
                    form.add_error(None, erreur)
            else:
                messages.success(request, f"Vente #{vente.id} corrigée.")
                return redirect('vente:corrections_ventes')
    else:
        form = CorrectionVenteGroupeForm(initial={
            'prix_vente_unitaire': vente.prix_vente_unitaire,
            'quantite': vente.quantite,
        })

    historique = (
        CorrectionAdministrative.objects
        .filter(
            content_type=ContentType.objects.get_for_model(Vente),
            object_id=vente.id,
            type_correction__in=TYPES_CORRECTION_VENTE,
        )
        .select_related('utilisateur')
        .order_by('-date_action')
    )

    return render(request, 'vente/corrections/corriger.html', {
        'form': form,
        'vente': vente,
        'lot': vente.detail_distribution.lot,
        'kilo_perdu': vente.kilo_perdu,
        'historique': historique,
    })


@login_required
@user_passes_test(est_correcteur_ventes)
def historique_corrections_ventes(request):
    corrections = (
        CorrectionAdministrative.objects
        .filter(type_correction__in=TYPES_CORRECTION_VENTE)
        .select_related('utilisateur')
        .order_by('-date_action')
    )
    page_obj = Paginator(corrections, 30).get_page(request.GET.get('page'))
    return render(request, 'vente/corrections/historique.html', {'page_obj': page_obj})
