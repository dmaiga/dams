"""Seuils d'alerte et libellés des dashboards BI.

Toutes les valeurs viennent de docs/docs_bi/bi/07_Dictionnaire_KPI_Metier.md (cibles) et
08_Dashboard_Catalog.md (codes couleur). Les vues et templates lisent ces constantes plutôt
que de coder les seuils en dur (Étape 2 de la mission BI, décision actée).

Statuts : "vert" (bon), "jaune" (alerte), "rouge" (critique) — cohérent avec 🟢/🟡/🔴 du
Dashboard_Catalog. `None` (donnée absente, ex. division par zéro dans une vue dbt) → "neutre".
"""

DASHBOARDS = [
    ("sante", "Santé Globale"),
    ("produits", "Rentabilité Produit"),
    ("agents", "Agents"),
    ("depenses", "Dépenses"),
    ("stock", "Stock & Fournisseur"),
]

# Dashboard Agents : types d'agents réellement soumis à l'objectif terrain/vente (cf.
# agents_cibles dans vw_performance_agent(_semaine).sql) — sert le filtre type_agent.
TYPE_AGENT_CHOICES = [
    ("terrain", "Terrain"),
    ("agent_gros", "Agent gros"),
    ("agent_polivalent", "Agent polivalent"),
]

VERT = "vert"
JAUNE = "jaune"
ROUGE = "rouge"
NEUTRE = "neutre"

# --- Dashboard 1 : Santé Globale (KPI-001 à 009) ---
MARGE_PCT_MIN = 45
MARGE_PCT_MAX = 55
SALAIRES_PCT_CIBLE = 25
SALAIRES_PCT_MAX = 35
DEPENSES_PCT_ALERTE = 15
DEPENSES_PCT_MAJEUR = 20
RENTABILITE_NETTE_CIBLE = 500_000
MARGE_BRUTE_CIBLE = 3_000_000

# --- Dashboard 2 : Rentabilité Produit (KPI-101 à 106) ---
MARGE_PCT_PRODUIT_MIN = 40
MARGE_PCT_PRODUIT_MAX = 60
ROTATION_STOCK_RAPIDE = 2
ROTATION_STOCK_MORT = 0.5

# --- Dashboard "Agents", volet équipes/superviseurs (KPI-201 à 206) ---
CA_MOYEN_AGENT_CIBLE = 500_000

# --- Dashboard "Agents", volet agents (KPI-301 à 306) ---
RENTABILITE_AGENT_CIBLE = 100_000

STATUT_OBJECTIF_LABELS = {
    "atteint": "✅ Atteint",
    "proche": "⚠️ Proche",
    "sous_objectif": "❌ Sous objectif",
}
STATUT_OBJECTIF_COULEURS = {
    "atteint": VERT,
    "proche": JAUNE,
    "sous_objectif": ROUGE,
}

# --- Dashboard 5 : Stock & Fournisseur (KPI-401 à 405) ---
VALEUR_STOCK_CIBLE = 3_000_000
VALEUR_STOCK_ALERTE = 5_000_000
JOURS_STOCK_MIN = 30
JOURS_STOCK_MAX = 45
JOURS_STOCK_MORT = 60
MARGE_PCT_FOURNISSEUR_MIN = 45
MARGE_PCT_FOURNISSEUR_MAX = 55
MARGE_PCT_FOURNISSEUR_FAIBLE = 30


def _entre(valeur, mini, maxi):
    return mini <= valeur <= maxi


def statut_marge_pct(valeur):
    if valeur is None:
        return NEUTRE
    if _entre(valeur, MARGE_PCT_MIN, MARGE_PCT_MAX):
        return VERT
    return JAUNE if valeur > 0 else ROUGE


def statut_rentabilite_nette(valeur):
    if valeur is None:
        return NEUTRE
    if valeur < 0:
        return ROUGE
    return VERT if valeur >= RENTABILITE_NETTE_CIBLE else JAUNE


def statut_salaires_pct(valeur):
    if valeur is None:
        return NEUTRE
    if valeur > SALAIRES_PCT_MAX:
        return ROUGE
    return VERT if valeur <= SALAIRES_PCT_CIBLE else JAUNE


def statut_depenses_pct(valeur):
    if valeur is None:
        return NEUTRE
    if valeur > DEPENSES_PCT_MAJEUR:
        return ROUGE
    return JAUNE if valeur > DEPENSES_PCT_ALERTE else VERT


def statut_marge_produit(marge, marge_pct):
    if marge is not None and marge < 0:
        return ROUGE
    if marge_pct is None:
        return NEUTRE
    return VERT if _entre(marge_pct, MARGE_PCT_PRODUIT_MIN, MARGE_PCT_PRODUIT_MAX) else JAUNE


def statut_rotation_stock(valeur):
    if valeur is None:
        return NEUTRE
    if valeur < ROTATION_STOCK_MORT:
        return ROUGE
    return VERT if valeur >= ROTATION_STOCK_RAPIDE else JAUNE


def statut_rentabilite_agent(valeur):
    if valeur is None:
        return NEUTRE
    if valeur < 0:
        return ROUGE
    return VERT if valeur >= RENTABILITE_AGENT_CIBLE else JAUNE


def statut_ca_moyen_agent(valeur):
    """Sprint-11 (18/08/2026) : CA_MOYEN_AGENT_CIBLE existait déjà (fiche détail superviseur) mais
    n'était branché nulle part avant ce sprint."""
    if valeur is None:
        return NEUTRE
    if valeur < 0:
        return ROUGE
    return VERT if valeur >= CA_MOYEN_AGENT_CIBLE else JAUNE


def statut_objectif_agent(statut_50kg):
    return STATUT_OBJECTIF_COULEURS.get(statut_50kg, NEUTRE)


def statut_valeur_stock(valeur):
    if valeur is None:
        return NEUTRE
    if valeur > VALEUR_STOCK_ALERTE:
        return ROUGE
    return VERT if valeur <= VALEUR_STOCK_CIBLE else JAUNE


def statut_jours_stock(valeur):
    if valeur is None:
        return NEUTRE
    if valeur > JOURS_STOCK_MORT:
        return ROUGE
    return VERT if valeur < JOURS_STOCK_MIN else JAUNE


def statut_marge(marge, marge_pct):
    if marge is not None and marge < 0:
        return ROUGE
    if marge_pct is None:
        return NEUTRE
    if marge_pct < MARGE_PCT_FOURNISSEUR_FAIBLE:
        return ROUGE
    return VERT if _entre(marge_pct, MARGE_PCT_FOURNISSEUR_MIN, MARGE_PCT_FOURNISSEUR_MAX) else JAUNE
