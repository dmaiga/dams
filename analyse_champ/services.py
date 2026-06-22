import os

import requests

# URL de base pour toutes les requêtes vers l'API Django
BASE_API = os.getenv('API_URL')
BASE_URL = f'{BASE_API}/api'

def fetch_json(endpoint, params=None):
    """
    Fonction utilitaire centrale pour effectuer les requêtes GET.
    - endpoint: Le chemin de l'URL (ex: 'dashboard/')
    - params: Dictionnaire des paramètres de filtrage (ex: {'period': 'month'})
    - raise_for_status: Lève une exception si le serveur renvoie une erreur (4xx ou 5xx).
    """
    response = requests.get(
        f'{BASE_URL}/{endpoint}',
        params=params,
        timeout=10  # Protection : arrête la requête après 10 secondes
    )
    # Vérifie si la requête a réussi (code 200)
    response.raise_for_status()
    
    # Retourne les données décodées au format JSON
    return response.json()


# =========================
# DASHBOARD
# =========================

def get_dashboard(params=None):
    """Récupère les statistiques globales (revenus, dépenses, etc.) du tableau de bord."""
    return fetch_json('dashboard/', params=params)


# =========================
# OPERATIONS
# =========================

def get_operations(params=None):
    """Récupère la liste des opérations financières (revenus, dépenses, stocks)."""
    return fetch_json('operations/', params=params)

def get_operation_detail(pk):

    return fetch_json(
        f'operations/{pk}/'
    )

# =========================
# CATEGORIES
# =========================

def get_categories():

    return fetch_json(
        'categories/'
    )

# =========================
# PRODUITS
# =========================

def get_products(params=None):
    """Récupère la liste complète des produits enregistrés."""
    return fetch_json('produits/', params=params)


def get_product_detail(pk):
    """Récupère les détails complets d'un produit spécifique via son identifiant (pk)."""
    return fetch_json(f'produits/{pk}/')


# =========================
# AGENTS
# =========================

def get_agents(params=None):
    """Récupère les performances des agents (quantités attachées, totaux)."""
    return fetch_json('agents/', params=params)

# =========================
# RAPPORTS
# =========================
def get_superviseurs():
    return fetch_json(
        'superviseurs/'
    )

def get_rapports(params=None):
    return fetch_json(
        'rapports/',
        params=params
    )

def get_rapport_detail(pk):
    return fetch_json(
        f'rapports/{pk}/'
    )


# ── Cultures ──────────────────────────────────────────────────
def get_fiches(params=None):
    return fetch_json("cultures/", params=params)

def get_fiche_detail(pk):
    return fetch_json(f"cultures/{pk}/")

def get_connaissances():
    return fetch_json("cultures/connaissances/")
