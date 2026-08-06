import re

from django.shortcuts import render
from analyse_champ.services import (
    DamsAgroAPIError,
    get_dashboard,

    get_operations,
    get_operation_detail,
    get_engagement_detail,

    get_categories,
    get_products,
    get_product_detail,

    get_agents,

    get_superviseurs,
    get_rapports,
    get_rapport_detail,

    get_fiches,
    get_fiche_detail,
    get_rapports_culture,
    get_connaissances
)

# Repère l'id d'engagement dams_agro accolé par `engagements/services.py`
# (dams_agro, contrat figé) à la fin du label ("... #17") ou dans la note
# générique d'une avance ("... engagement #17.") d'une Operation générée
# automatiquement — voir get_engagement_detail.
ENGAGEMENT_ID_PATTERN = re.compile(r'#(\d+)')


def build_filters(request):
    """
    Fonction utilitaire qui extrait les paramètres de filtrage de la requête HTTP
    pour les transformer en un dictionnaire utilisable par les services API.

    `period=custom` n'est PAS transmis à dams_agro : ce n'est pas une valeur
    reconnue par son `DateFilterMixin` (seulement today/week/month/year,
    voir docs/api/api_structure.md côté dams_agro) — dans ce cas seuls
    date_from/date_to (saisis par l'utilisateur) doivent filtrer.
    """
    params = {}
    period = request.GET.get('period')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if period and period != 'custom':
        params['period'] = period
    if date_from: params['date_from'] = date_from
    if date_to: params['date_to'] = date_to

    return params

# =========================
# DASHBOARD
# =========================
def dashboard_view(request):
    """Récupère les données du dashboard et les envoie au template."""
    params = build_filters(request)
    dashboard = get_dashboard(params=params)
    
    return render(request, 'dashboard.html', {'dashboard': dashboard})

# =========================
# OPERATIONS
# =========================
def operation_list_view(request):

    # Filtres de période seuls (period/date_from/date_to) — servent à la
    # fois à la liste et aux KPIs revenus/dépenses ci-dessous. `type`/
    # `categorie` ne s'appliquent qu'à la liste : /api/dashboard/ ne les
    # accepte pas (voir docs/api/api_structure.md côté dams_agro).
    periode_params = build_filters(
        request
    )

    # Défaut local à cette vue (pas dans build_filters, réutilisée ailleurs
    # sans ce défaut) : premier chargement de page, aucun filtre encore
    # soumis — "Aujourd'hui" est présélectionné dans le formulaire, la
    # requête doit refléter la même période dès le premier affichage.
    if 'period' not in request.GET and not periode_params.get('date_from'):
        periode_params['period'] = 'today'

    operation_type = request.GET.get(
        'type'
    )

    categorie = request.GET.get(
        'categorie'
    )

    operations_params = dict(periode_params)

    if operation_type:

        operations_params['type'] = (
            operation_type
        )

    if categorie:

        operations_params['categorie'] = (
            categorie
        )

    operations = get_operations(
        params=operations_params
    )

    categories = get_categories()

    kpis = get_dashboard(
        params=periode_params
    )

    context = {

        'operations': operations,

        'categories': categories,

        'kpis': kpis,

        'selected_type': (
            operation_type
        ),

        'selected_categorie': (
            categorie
        ),

        'selected_period': request.GET.get('period', ''),
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
    }

    return render(
        request,
        'finance_champs/operations/list.html',
        context
    )

def operation_detail_view(
    request,
    pk
):

    operation = (
        get_operation_detail(
            pk
        )
    )

    # Si cette Operation a été générée automatiquement pour un engagement
    # superviseur ↔ champ, va chercher le commentaire réel sur
    # l'EngagementFinancier lié — le `note` de l'Operation elle-même ne
    # contient qu'un texte générique pour une avance (voir
    # get_engagement_detail). L'id est repéré dans `note` (cas avance,
    # ".. l'engagement #17.") ou dans `label` (cas remboursement,
    # "Remboursement — ... #17").
    engagement = None
    match = (
        ENGAGEMENT_ID_PATTERN.search(operation.get('note') or '')
        or ENGAGEMENT_ID_PATTERN.search(operation.get('label') or '')
    )
    if match:
        try:
            engagement = get_engagement_detail(match.group(1))
        except DamsAgroAPIError:
            engagement = None

    context = {
        'operation': operation,
        'engagement': engagement,
    }

    return render(
        request,
        'finance_champs/operations/detail.html',
        context
    )




# =========================
# PRODUITS
# =========================
def product_list_view(request):
    """Récupère la liste des produits avec les filtres de période appliqués."""
    params = build_filters(request)
    products = get_products(params=params)
    
    return render(request, 'finance_champs/products/list.html', {'products': products})

def product_detail_view(request, pk):
    """Récupère les détails d'un produit spécifique via son ID (pk)."""
    product = get_product_detail(pk)
    
    return render(request, 'finance_champs/products/detail.html', {'product': product})

# =========================
# AGENTS
# =========================
def agent_list_view(request):
    """Récupère la liste des performances des agents avec les filtres de période."""
    params = build_filters(request)
    agents = get_agents(params=params)
    
    return render(request, 'finance_champs/agents/list.html', {'agents': agents})
# =========================
# RAPPORTS
# =========================

def rapport_list_view(request):
    params = build_filters(request)
    superviseur = request.GET.get(
        'superviseur'
    )
    if superviseur:
        params['superviseur'] = superviseur
    rapports = get_rapports(
        params=params
    )
    superviseurs = get_superviseurs()
    context = {
        'rapports': rapports,
        'superviseurs': superviseurs['results'],
    }
    return render(
        request,
        'rapport_journalier/list.html',
        context
    )

def rapport_detail_view(request,pk):
    rapport = get_rapport_detail(pk)
    context = {
        'rapport': rapport
    }
    return render(
        request,
        'rapport_journalier/detail.html',
        context
    )

# =========================
# CULTURE
# =========================
def fiche_list_view(request):
    params = build_filters(request)
    for key in ("annee", "mois"):
        val = request.GET.get(key)
        if val:
            params[key] = val
    fiches = get_fiches(params=params)
    return render(request, "cultures_champs/list.html", {"fiches": fiches})

def fiche_detail_view(request, pk):
    fiche = get_fiche_detail(pk)
    return render(request, "cultures_champs/detail.html", {"fiche": fiche})

def rapports_culture_list_view(request):
    params = {}
    val = request.GET.get("culture")
    if val:
        params["culture"] = val
    rapports = get_rapports_culture(params=params)
    return render(request, "cultures_champs/rapports.html", {"rapports": rapports})

def connaissances_view(request):
    connaissances = get_connaissances()
    return render(request, "cultures_champs/connaissances.html",
                  {"connaissances": connaissances})