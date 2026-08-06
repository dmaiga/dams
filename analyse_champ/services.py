import logging
import os

import requests

logger = logging.getLogger(__name__)

# URL de base pour toutes les requêtes vers l'API Django
BASE_API = os.getenv('API_URL')
BASE_URL = f'{BASE_API}/api'

# Clé API dams_agro — uniquement nécessaire pour les endpoints en écriture
# (/api/engagements/...). Tous les GET de ce fichier restent non authentifiés,
# cohérent avec le contrat dams_agro (lecture seule ouverte à `dams`). Même
# nom de variable que côté dams_agro (secret partagé entre les deux repos).
DAMS_DISTRIBUTION_API_KEY = os.getenv('DAMS_DISTRIBUTION_API_KEY')


class DamsAgroAPIError(Exception):
    """
    Erreur lors d'un appel à l'API dams_agro : réseau, timeout, HTTP ou
    métier (validation refusée côté dams_agro). Toujours levée — jamais
    avalée — car l'appelant (finance.services) ne doit créer aucune écriture
    locale tant que la synchronisation dams_agro n'est pas confirmée (voir
    finance/APP_FINANCE.md § Engagements superviseur ↔ champ).
    """


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

def get_rapports_culture(params=None):
    return fetch_json("cultures/rapports/", params=params)

def get_connaissances():
    return fetch_json("cultures/connaissances/")


# =========================
# ENGAGEMENTS SUPERVISEUR ↔ CHAMP (écriture — seule exception au GET-only
# de ce module, voir analyse_champ/APP_ANALYSE_CHAMP.md)
# =========================

def _post_json(endpoint, payload):
    """
    Équivalent en écriture de fetch_json, avec gestion d'erreurs explicite
    (réseau, timeout, HTTP) — contrairement à fetch_json, aucune exception
    n'est laissée remonter brute : tout est traduit en DamsAgroAPIError,
    avec journalisation, pour que l'appelant sache précisément qu'aucune
    écriture locale ne doit avoir lieu.
    """
    headers = {'X-Api-Key': DAMS_DISTRIBUTION_API_KEY} if DAMS_DISTRIBUTION_API_KEY else {}

    try:
        response = requests.post(
            f'{BASE_URL}/{endpoint}',
            json=payload,
            headers=headers,
            timeout=10,
        )
    except requests.exceptions.Timeout as exc:
        logger.error("Timeout dams_agro sur POST %s (payload=%s)", endpoint, payload)
        raise DamsAgroAPIError(
            "dams_agro n'a pas répondu à temps (timeout)."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("Connexion impossible à dams_agro sur POST %s (payload=%s)", endpoint, payload)
        raise DamsAgroAPIError(
            "Impossible de joindre dams_agro (problème réseau)."
        ) from exc
    except requests.exceptions.RequestException as exc:
        logger.error("Erreur requête dams_agro sur POST %s : %s", endpoint, exc)
        raise DamsAgroAPIError(f"Erreur de communication avec dams_agro : {exc}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        logger.error(
            "dams_agro a refusé POST %s (code %s) : %s",
            endpoint, response.status_code, detail
        )
        raise DamsAgroAPIError(f"dams_agro a refusé la requête ({response.status_code}) : {detail}")

    return response.json()


def _request_engagements(url, params=None):
    """
    Équivalent en lecture de _post_json, pour l'app engagements exclusivement :
    contrairement aux GET des autres apps de ce module (session, non
    authentifiés côté dams), les endpoints `engagements` sont réservés à DAMS
    Distribution et authentifiés par X-Api-Key — y compris en GET (voir
    docs/api/api_structure.md côté dams_agro : "Consommateur : DAMS
    Distribution exclusivement... Auth : en-tête X-Api-Key... pas de
    session"). `url` est soit un endpoint absolu de premier appel, soit l'URL
    `next` de pagination renvoyée telle quelle par dams_agro (auquel cas
    `params` est ignoré, déjà inclus dedans). Même traduction d'erreurs que
    _post_json : jamais d'exception brute, toujours DamsAgroAPIError.
    """
    headers = {'X-Api-Key': DAMS_DISTRIBUTION_API_KEY} if DAMS_DISTRIBUTION_API_KEY else {}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
    except requests.exceptions.Timeout as exc:
        logger.error("Timeout dams_agro sur GET %s", url)
        raise DamsAgroAPIError("dams_agro n'a pas répondu à temps (timeout).") from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("Connexion impossible à dams_agro sur GET %s", url)
        raise DamsAgroAPIError("Impossible de joindre dams_agro (problème réseau).") from exc
    except requests.exceptions.RequestException as exc:
        logger.error("Erreur requête dams_agro sur GET %s : %s", url, exc)
        raise DamsAgroAPIError(f"Erreur de communication avec dams_agro : {exc}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        logger.error("dams_agro a refusé GET %s (code %s) : %s", url, response.status_code, detail)
        raise DamsAgroAPIError(f"dams_agro a refusé la requête ({response.status_code}) : {detail}")

    return response.json()


def get_engagements_champ_superviseur(reference_superviseur):
    """
    Tous les engagements de CE superviseur côté dams_agro — GET
    /api/engagements/?reference_superviseur=... Utilisé pour la
    réconciliation du Constat 1 (sprint-06) : voir
    finance.services.synchroniser_engagements_champ. Chaque élément contient
    notamment `id` (== Depense.reference_dams_agro côté dams) et
    `reste_a_rembourser` (DecimalField rendu string sur cet endpoint —
    contrairement à /api/engagements/dashboard/, qui rend des float, voir
    docs/api/api_structure.md côté dams_agro).

    ⚠️ Contrairement au principe général "PageNumberPagination, 20/page"
    documenté pour le reste de l'API dams_agro, cet endpoint (et plus
    généralement toute l'app `engagements`) est un `APIView` brut
    (`engagements/api_views.py::EngagementListCreateAPIView`), pas un
    `ListAPIView` — il renvoie une **liste JSON directe**, jamais
    `{count, results, next}`. Vérifié sur le code source dams_agro le
    06/08/2026 après une AttributeError en usage réel (`list.get`) causée
    par une première implémentation qui supposait la pagination générale.
    """
    url = f'{BASE_URL}/engagements/'
    params = {'reference_superviseur': reference_superviseur}
    return _request_engagements(url, params)


def get_engagement_detail(engagement_id):
    """
    GET /api/engagements/<id>/ — détail d'un engagement, avec ses
    remboursements imbriqués (`EngagementFinancierDetailSerializer`),
    authentifié X-Api-Key comme le reste de l'app `engagements`.

    Utilisé par la vue Direction `operation_detail_view` (opérations
    finance_champs) pour retrouver le **vrai** commentaire métier d'un
    engagement à partir de l'`Operation` générée automatiquement côté
    dams_agro : cette Operation a son propre `note`, mais pour une avance de
    trésorerie il ne contient qu'un message générique ("Généré
    automatiquement depuis l'engagement #N"), jamais le commentaire que le
    superviseur a saisi à la création — celui-ci n'existe que sur
    `EngagementFinancier.note`/`label` (voir
    `dams_champs/engagements/services.py::creer_engagement`).
    """
    url = f'{BASE_URL}/engagements/{engagement_id}/'
    return _request_engagements(url)


def creer_engagement_dams_agro(*, nature, montant, commentaire, reference_superviseur):
    """
    POST /api/engagements/ — crée l'engagement côté dams_agro (source de
    vérité pour le champ). `nature` : 'avance_tresorerie' ou 'depense_compte'.
    Retourne le dict JSON de l'EngagementFinancier créé (dont 'id').
    """
    payload = {
        'nature': nature,
        'montant_initial': str(montant),
        'label': (commentaire or nature)[:255],
        'reference_superviseur': reference_superviseur,
        'note': commentaire or '',
    }
    return _post_json('engagements/', payload)
