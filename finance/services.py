from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Agent, Depense, Recouvrement, RecouvrementSuperviseur, VersementBancaire

SEUIL_ALERTE_SOLDE = Decimal("25000")

# Point de départ de finance/ comme source de vérité (décision n°14, sprint-03) :
# l'historique antérieur est jugé incohérent (ancien paradigme superviseur,
# introduction tardive du rôle ROT) — mdmaiga a choisi de ne pas le reprendre
# plutôt que de composer avec des données peu fiables. Tout Recouvrement/
# RecouvrementSuperviseur/Depense/VersementBancaire antérieur est ignoré.
DATE_DEBUT_FINANCE = date(2026, 8, 1)


def solde_superviseur(superviseur, date_fin=None):
    """
    Cash actuellement détenu par CE superviseur, pas encore remis à un acteur
    admin (ROT ou direction). Calcul dynamique depuis DATE_DEBUT_FINANCE (pas
    de "solde d'ouverture" ni de clôture) — l'historique antérieur est ignoré,
    voir décision n°14. Le calcul mélangeait auparavant ce solde avec des
    Depense et VersementBancaire qui sont en réalité des événements de la
    caisse globale une fois l'argent mutualisé, pas des événements du
    superviseur (décision n°13, docs/sprints/sprint-03.md).

    Une Depense faite par CE superviseur lui-même (`peut_faire_depense`,
    avant remise) réduit ce solde ; une Depense faite par un ROT/direction
    (après mutualisation) réduit `solde_caisse_globale`, pas celui-ci.
    """
    if date_fin is None:
        date_fin = timezone.localdate()

    encaissements = Recouvrement.objects.filter(
        superviseur=superviseur,
        date_recouvrement__date__gte=DATE_DEBUT_FINANCE,
        date_recouvrement__date__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant_recouvre"), Decimal("0.00")))["total"]

    depenses_perso = Depense.objects.filter(
        effectue_par=superviseur,
        date_depense__gte=DATE_DEBUT_FINANCE,
        date_depense__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    deja_remis = RecouvrementSuperviseur.objects.filter(
        superviseur=superviseur,
        date_recouvrement__date__gte=DATE_DEBUT_FINANCE,
        date_recouvrement__date__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    solde = encaissements - depenses_perso - deja_remis

    return {
        "superviseur": superviseur,
        "date_fin": date_fin,
        "encaissements": encaissements,
        "depenses": depenses_perso,
        "deja_remis": deja_remis,
        "solde": solde,
        "alerte": solde >= SEUIL_ALERTE_SOLDE,
    }


def lister_soldes_superviseurs(date_fin=None):
    superviseurs = Agent.objects.filter(type_agent='entrepot', est_actif=True).select_related('user')
    return [solde_superviseur(superviseur, date_fin) for superviseur in superviseurs]


def solde_caisse_globale(date_fin=None):
    """
    Cash détenu par les acteurs admin (ROT/direction) une fois la recette de
    tous les superviseurs mutualisée : ce qu'ils ont reçu, moins les dépenses
    et versements sur la période. Jamais filtré par `superviseur` —
    `VersementBancaire.superviseur` est un champ historique dupliquant
    `effectue_par` (même rôle : qui a effectué l'action), pas une attribution
    à un superviseur source (voir sprint-03, décision n°13). Historique
    antérieur à DATE_DEBUT_FINANCE ignoré (décision n°14).

    `depenses` = TOUTES les Depense sur la période, quel que soit `effectue_par`
    (décision n°15) : dans les faits, seul un superviseur (Abdoulaye Kone,
    ancien paradigme) en saisit actuellement, aucun ROT/direction. Restreindre
    à `effectue_par__type_agent__in=['rot','direction']` masquait ces dépenses
    réelles du KPI caisse globale. `solde_superviseur` continue par ailleurs de
    compter les dépenses personnelles de CE superviseur dans son propre solde
    (double affichage assumé, pas un double décompte comptable — voir décision
    n°15).
    """
    if date_fin is None:
        date_fin = timezone.localdate()

    recouvre = RecouvrementSuperviseur.objects.filter(
        date_recouvrement__date__gte=DATE_DEBUT_FINANCE,
        date_recouvrement__date__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    depenses = Depense.objects.filter(
        date_depense__gte=DATE_DEBUT_FINANCE,
        date_depense__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    versements = VersementBancaire.objects.filter(
        date_versement_reelle__date__gte=DATE_DEBUT_FINANCE,
        date_versement_reelle__date__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant_vente"), Decimal("0.00")))["total"]

    return {
        "date_fin": date_fin,
        "recouvre": recouvre,
        "depenses": depenses,
        "versements": versements,
        "solde": recouvre - depenses - versements,
    }
