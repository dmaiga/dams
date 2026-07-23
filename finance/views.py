from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    Agent, Depense, Recouvrement, RecouvrementSuperviseur, RecuVersement, VersementBancaire,
)

from finance.forms import (
    DepenseFinanceForm, RecouvrementSuperviseurForm, RecouvrementVersementFormSet,
    VersementBancaireForm,
)
from finance.services import DATE_DEBUT_FINANCE, lister_soldes_superviseurs, solde_caisse_globale, solde_superviseur


def _acces_finance(agent):
    return agent.est_direction


def _acces_depense(agent):
    return agent.est_direction or agent.peut_faire_depense


def _get_date_solde(request):
    """Date de référence du calcul de solde ("solde à la date du ..."), aujourd'hui par défaut."""
    date_fin = request.GET.get('date_fin')
    return date.fromisoformat(date_fin) if date_fin else timezone.localdate()


def _get_periode_mouvements(request):
    """
    Fenêtre libre de consultation de l'historique des mouvements (page détail).
    Jamais avant DATE_DEBUT_FINANCE : le solde affiché juste au-dessus n'en
    tient de toute façon pas compte (décision n°14, sprint-03).
    """
    aujourdhui = timezone.localdate()
    debut_defaut = max(aujourdhui.replace(day=1), DATE_DEBUT_FINANCE)

    mvt_debut = request.GET.get('mvt_debut') or debut_defaut.isoformat()
    mvt_fin = request.GET.get('mvt_fin') or aujourdhui.isoformat()

    return max(date.fromisoformat(mvt_debut), DATE_DEBUT_FINANCE), date.fromisoformat(mvt_fin)


@login_required
def dashboard_finance(request):
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    date_fin = _get_date_solde(request)
    soldes = lister_soldes_superviseurs(date_fin)
    caisse = solde_caisse_globale(date_fin)

    context = {
        'soldes': soldes,
        'caisse': caisse,
        'date_fin': date_fin,
        'nombre_alertes': sum(1 for s in soldes if s['alerte']),
        'page_title': 'Solde des superviseurs',
    }
    return render(request, 'finance/dashboard.html', context)


@login_required
def detail_solde_superviseur(request, pk):
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    superviseur = get_object_or_404(Agent, pk=pk, type_agent='entrepot')

    date_solde = _get_date_solde(request)
    solde = solde_superviseur(superviseur, date_solde)

    mvt_debut, mvt_fin = _get_periode_mouvements(request)

    mouvements = sorted(
        [
            {'type': 'encaissement', 'date': r.date_recouvrement, 'montant': r.montant_recouvre, 'objet': r}
            for r in Recouvrement.objects.filter(
                superviseur=superviseur,
                date_recouvrement__date__gte=mvt_debut,
                date_recouvrement__date__lte=mvt_fin,
            )
        ] + [
            {
                'type': 'depense',
                'date': timezone.make_aware(datetime.combine(d.date_depense, datetime.min.time())),
                'montant': -d.montant,
                'objet': d,
            }
            for d in Depense.objects.filter(
                effectue_par=superviseur,
                date_depense__gte=mvt_debut,
                date_depense__lte=mvt_fin,
            )
        ] + [
            {'type': 'remise', 'date': rs.date_recouvrement, 'montant': -rs.montant, 'objet': rs}
            for rs in RecouvrementSuperviseur.objects.filter(
                superviseur=superviseur,
                date_recouvrement__date__gte=mvt_debut,
                date_recouvrement__date__lte=mvt_fin,
            )
        ],
        key=lambda m: m['date'],
        reverse=True,
    )
    # Pas de VersementBancaire ici : une fois la recette remise (RecouvrementSuperviseur),
    # l'argent est mutualisé — le versement est un événement de la caisse globale,
    # pas de ce superviseur (voir finance/services.py::solde_caisse_globale).

    paginator = Paginator(mouvements, 30)
    mouvements_page = paginator.get_page(request.GET.get('page', 1))

    context = {
        'superviseur': superviseur,
        'solde': solde,
        'mouvements': mouvements_page,
        'date_fin': date_solde,
        'mvt_debut': mvt_debut,
        'mvt_fin': mvt_fin,
        'page_title': f'Solde — {superviseur.full_name}',
    }
    return render(request, 'finance/detail_solde_superviseur.html', context)


@login_required
def recouvrer_superviseur(request, pk):
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    superviseur = get_object_or_404(Agent, pk=pk, type_agent='entrepot')

    if request.method == 'POST':
        form = RecouvrementSuperviseurForm(request.POST)
        if form.is_valid():
            recouvrement = form.save(commit=False)
            recouvrement.rot = agent
            recouvrement.save()
            messages.success(request, f"Recette de {superviseur.full_name} recouvrée avec succès.")
            return redirect('finance:detail_solde_superviseur', pk=superviseur.pk)
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = RecouvrementSuperviseurForm(initial={'superviseur': superviseur})

    context = {
        'form': form,
        'superviseur': superviseur,
        'page_title': f'Recouvrer — {superviseur.full_name}',
    }
    return render(request, 'finance/recouvrer_superviseur.html', context)


@login_required
def recouvrement_versement_groupe(request):
    """
    Action groupée : pour chaque superviseur actif, recouvrement de la recette
    (réduit son solde individuel) + versement bancaire de la caisse mutualisée
    (+ reçu) en une seule soumission. Une ligne laissée vide (superviseur sans
    recette) n'est simplement pas traitée.

    Le montant préempli vient toujours du solde réel actuel
    (lister_soldes_superviseurs, calcul dynamique sur tout l'historique).
    """
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    soldes = lister_soldes_superviseurs()

    initial = [
        {
            'superviseur': s['superviseur'].pk,
            'montant': s['solde'] if s['solde'] > 0 else None,
        }
        for s in soldes
    ]

    if request.method == 'POST':
        formset = RecouvrementVersementFormSet(request.POST, request.FILES, initial=initial)
        if formset.is_valid():
            nb_traites = 0
            with transaction.atomic():
                for form in formset:
                    montant = form.cleaned_data.get('montant')
                    if not montant:
                        continue

                    superviseur = form.cleaned_data['superviseur']
                    montant_hors_vente = form.cleaned_data.get('montant_hors_vente') or Decimal('0.00')
                    recu = form.cleaned_data.get('recu')
                    maintenant = timezone.now()

                    RecouvrementSuperviseur.objects.create(
                        superviseur=superviseur,
                        rot=agent,
                        montant=montant,
                        date_recouvrement=maintenant,
                    )
                    versement = VersementBancaire.objects.create(
                        effectue_par=agent,
                        montant_vente=montant,
                        montant_hors_vente=montant_hors_vente,
                        date_versement_reelle=maintenant,
                    )
                    if recu:
                        RecuVersement.objects.create(
                            versement=versement,
                            fichier=recu,
                            description=f"Reçu pour versement {versement.id}",
                        )
                    nb_traites += 1

            if nb_traites:
                messages.success(
                    request,
                    f"{nb_traites} superviseur(s) recouvré(s) et versé(s) avec succès."
                )
            else:
                messages.info(request, "Aucun montant saisi — rien à traiter.")
            return redirect('finance:dashboard_finance')
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        formset = RecouvrementVersementFormSet(initial=initial)

    lignes = list(zip(formset.forms, soldes))

    context = {
        'formset': formset,
        'lignes': lignes,
        'page_title': 'Recouvrement + versement groupé',
    }
    return render(request, 'finance/recouvrement_versement_groupe.html', context)


@login_required
def creer_versement(request):
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = VersementBancaireForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(effectue_par=agent)
            messages.success(request, "Versement bancaire enregistré.")
            return redirect('finance:historique_versements')
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = VersementBancaireForm()

    return render(request, 'finance/creer_versement.html', {'form': form, 'page_title': 'Nouveau versement'})


@login_required
def creer_depense(request):
    agent = request.user.agent
    if not _acces_depense(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = DepenseFinanceForm(request.POST)
        if form.is_valid():
            form.save(agent=agent)
            messages.success(request, "Dépense enregistrée.")
            return redirect('finance:historique_depenses')
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = DepenseFinanceForm()
        if not agent.est_direction:
            form.fields.pop('agent_cible')

    return render(request, 'finance/creer_depense.html', {'form': form, 'page_title': 'Nouvelle dépense'})


@login_required
def historique_versements(request):
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    versements = (
        VersementBancaire.objects
        .select_related('effectue_par', 'effectue_par__user')
        .prefetch_related('recus')
        .order_by('-date_versement_reelle')
    )
    return render(request, 'finance/historique_versements.html', {
        'versements': versements,
        'page_title': 'Historique des versements',
    })


@login_required
def historique_depenses(request):
    agent = request.user.agent
    if not _acces_finance(agent):
        return redirect('access_denied')

    depenses = (
        Depense.objects
        .select_related('effectue_par', 'effectue_par__user')
        .order_by('-date_depense')
    )
    return render(request, 'finance/historique_depenses.html', {
        'depenses': depenses,
        'page_title': 'Historique des dépenses',
    })
