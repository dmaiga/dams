from django.shortcuts import render
from analyse_champ.services import (
    get_dashboard,

    get_operations,
    get_operation_detail,

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

def build_filters(request):
    """
    Fonction utilitaire qui extrait les paramètres de filtrage de la requête HTTP
    pour les transformer en un dictionnaire utilisable par les services API.
    """
    params = {}
    period = request.GET.get('period')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if period: params['period'] = period
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

    params = build_filters(
        request
    )

    operation_type = request.GET.get(
        'type'
    )

    categorie = request.GET.get(
        'categorie'
    )

    if operation_type:

        params['type'] = (
            operation_type
        )

    if categorie:

        params['categorie'] = (
            categorie
        )

    operations = get_operations(
        params=params
    )

    categories = get_categories()

    context = {

        'operations': operations,

        'categories': categories,

        'selected_type': (
            operation_type
        ),

        'selected_categorie': (
            categorie
        ),
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

    context = {
        'operation': operation
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