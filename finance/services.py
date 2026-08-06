import logging
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Agent, Depense, Recouvrement, RecouvrementSuperviseur, RemboursementChamp, VersementBancaire

from analyse_champ.services import (
    DamsAgroAPIError,
    creer_engagement_dams_agro,
    get_engagements_champ_superviseur,
)

logger = logging.getLogger(__name__)

SEUIL_ALERTE_SOLDE = Decimal("30000")

# Catégories Depense représentant un engagement superviseur ↔ champ
# (avance de trésorerie / dépense pour compte), synchronisées avec dams_agro.
CATEGORIES_ENGAGEMENT_CHAMP = ('AVANCE_CHAMP', 'DEPENSE_CHAMP')

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
    de clôture) — l'historique antérieur est ignoré, voir décision n°14. Le
    calcul mélangeait auparavant ce solde avec des Depense et VersementBancaire
    qui sont en réalité des événements de la caisse globale une fois l'argent
    mutualisé, pas des événements du superviseur (décision n°13,
    docs/sprints/sprint-03.md).

    Une Depense faite par CE superviseur lui-même (`peut_faire_depense`,
    avant remise) réduit ce solde ; une Depense faite par un ROT/direction
    (après mutualisation) réduit `solde_caisse_globale`, pas celui-ci.

    `Agent.ajustement_solde` (décision n°16, 2026-08-03) sert de solde
    d'ouverture manuel à DATE_DEBUT_FINANCE : la coupure nette de la décision
    n°14 peut créer une incohérence quand un superviseur détenait déjà du cash
    non remis juste avant la coupure (ex. recouvrement le 31/07 non remis,
    suivi d'une dépense le 01/08 — le calcul sans ajustement peut alors
    devenir négatif alors que le superviseur a bien assez de cash en main).
    `ajustement_solde` est un champ générique de `Agent`, déjà éditable dans
    l'admin (`list_editable`) et déjà utilisé pour un rôle équivalent côté
    ROT (`Agent.solde_rot`) — pas de champ dédié créé, réutilisation du
    mécanisme existant. Poser cette valeur une seule fois par superviseur
    concerné (montant réellement détenu, non remis, juste avant le
    01/08/2026) ; ne pas la modifier ensuite au fil de l'eau.

    Engagements superviseur ↔ champ (dams_agro, sprint intégration
    engagements) : une avance de trésorerie ou une dépense pour compte est
    une Depense normale (categorie AVANCE_CHAMP/DEPENSE_CHAMP) — déjà
    comptée dans `depenses_perso` ci-dessus, aucun terme supplémentaire
    nécessaire pour la création. Le remboursement, lui, n'a pas d'équivalent
    parmi les termes existants (Recouvrement est structurellement lié à un
    agent terrain, RecouvrementSuperviseur représente l'inverse — de l'argent
    remis PAR le superviseur) : `remboursements_champ` est le seul nouveau
    terme ajouté à cette formule unique (pas un second calcul concurrent).
    Effet net sur tout engagement en cours : -montant_initial (immédiat, via
    depenses_perso) + remboursé (via remboursements_champ) = -reste à
    rembourser, exactement la règle métier attendue.
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

    remboursements_champ = RemboursementChamp.objects.filter(
        depense__effectue_par=superviseur,
        date_remboursement__gte=DATE_DEBUT_FINANCE,
        date_remboursement__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    # Pour affichage Direction (distinguer engagements champ du reste des
    # dépenses perso, déjà inclus dans depenses_perso ci-dessus).
    engage_champ = Depense.objects.filter(
        effectue_par=superviseur,
        categorie__in=CATEGORIES_ENGAGEMENT_CHAMP,
        date_depense__gte=DATE_DEBUT_FINANCE,
        date_depense__lte=date_fin,
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    ajustement = superviseur.ajustement_solde or Decimal("0.00")

    solde = encaissements - depenses_perso - deja_remis + ajustement + remboursements_champ

    return {
        "superviseur": superviseur,
        "date_fin": date_fin,
        "encaissements": encaissements,
        "depenses": depenses_perso,
        "deja_remis": deja_remis,
        "ajustement": ajustement,
        "remboursements_champ": remboursements_champ,
        "engage_champ": engage_champ,
        "reste_a_rembourser_champ": engage_champ - remboursements_champ,
        "solde": solde,
        "alerte": solde > SEUIL_ALERTE_SOLDE,
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

    Exception : les Depense de categorie AVANCE_CHAMP/DEPENSE_CHAMP (engagements
    superviseur ↔ champ) sont exclues de ce total — ce ne sont pas des dépenses
    organisationnelles perdues mais des créances destinées à être remboursées ;
    les compter ici surestimerait durablement les dépenses de la caisse globale
    (le remboursement, lui, n'alimente que `solde_superviseur`, jamais cette
    fonction — voir son propre docstring).
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
    ).exclude(
        categorie__in=CATEGORIES_ENGAGEMENT_CHAMP
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


# =========================
# ENGAGEMENTS SUPERVISEUR ↔ CHAMP (dams_agro)
# =========================
#
# dams_agro est le seul système consommé en écriture (X-Api-Key,
# /api/engagements/...) — voir engagements/APP_ENGAGEMENTS.md côté dams_agro.
# Stratégie "remote-first" : l'appel dams_agro se fait TOUJOURS avant toute
# écriture locale (Depense/RemboursementChamp). En cas d'échec réseau/HTTP,
# aucune écriture locale n'a lieu — pas d'incohérence silencieuse entre les
# deux applications. Il n'y a pas de retry automatique (aucune infra
# Celery/APScheduler dans ce repo, confirmé) : un échec doit être ressaisi
# manuellement par le superviseur.

def reference_superviseur_dams_agro(superviseur):
    """
    Identifiant stable et unique transmis à dams_agro pour ce superviseur
    (champ texte libre côté dams_agro, aucun compte partagé entre les deux
    systèmes). Ne jamais faire varier cette valeur une fois utilisée — elle
    sert à retrouver les engagements de ce superviseur (GET
    /api/engagements/?reference_superviseur=...).
    """
    return str(superviseur.pk)


def creer_engagement_champ(*, superviseur, nature, montant, commentaire, date_depense=None):
    """
    Crée une avance de trésorerie ou une dépense pour le compte du champ.
    `nature` : 'AVANCE_CHAMP' ou 'DEPENSE_CHAMP' (categorie Depense).
    Lève ValidationError (montant invalide) ou DamsAgroAPIError (échec de
    synchronisation) — dans les deux cas, aucune Depense n'est créée.
    """
    if nature not in CATEGORIES_ENGAGEMENT_CHAMP:
        raise ValidationError("Nature d'engagement invalide.")
    if montant is None or montant <= 0:
        raise ValidationError("Le montant doit être supérieur à zéro.")

    nature_dams_agro = 'avance_tresorerie' if nature == 'AVANCE_CHAMP' else 'depense_compte'

    resultat = creer_engagement_dams_agro(
        nature=nature_dams_agro,
        montant=montant,
        commentaire=commentaire,
        reference_superviseur=reference_superviseur_dams_agro(superviseur),
    )

    return Depense.objects.create(
        effectue_par=superviseur,
        montant=montant,
        categorie=nature,
        note=(commentaire or '')[:255],
        date_depense=date_depense or timezone.localdate(),
        reference_dams_agro=resultat['id'],
    )


def synchroniser_engagements_champ(superviseur):
    """
    Réconciliation Constat 1 (sprint-06) : rattrape un remboursement
    d'engagement champ enregistré directement côté dams_agro (rôle `finance`
    de ce repo séparé, page propre à dams_agro) — que `dams` n'apprend
    autrement jamais, faute de webhook (dams_agro est un contrat figé,
    aucune modification n'y est possible, décision actée au sprint
    précédent). Déclenchée à l'entrée sur finance:mes_engagements_champ
    (décision de mdmaiga, 06/08/2026 : un clic suffit, pas de tâche planifiée
    ni de bouton séparé — le volume attendu est faible, un seul agent
    habilité).

    Ne compare que les engagements encore ouverts localement
    (`reste_a_rembourser_champ > 0`) : un engagement déjà soldé ici ne peut
    plus diverger. Pour chaque écart constaté (dams_agro montre moins de
    reste que `dams`), crée le `RemboursementChamp` manquant, sans référence
    dams_agro individuelle (on ne connaît que l'écart agrégé, pas le détail
    des remboursements distants qui l'ont produit).

    Best-effort : dams_agro injoignable ou en erreur ne doit jamais empêcher
    l'affichage de la page — l'échec est journalisé et avalé (même principe
    que lister_engagements_champ, qui elle ne fait aucun appel réseau).
    """
    a_verifier = [
        d for d in Depense.objects.filter(
            effectue_par=superviseur,
            categorie__in=CATEGORIES_ENGAGEMENT_CHAMP,
            reference_dams_agro__isnull=False,
        ).prefetch_related('remboursements_champ')
        if d.reste_a_rembourser_champ > 0
    ]
    if not a_verifier:
        return

    try:
        distants = get_engagements_champ_superviseur(reference_superviseur_dams_agro(superviseur))
    except DamsAgroAPIError as exc:
        logger.warning(
            "Synchronisation engagements champ impossible pour superviseur %s : %s",
            superviseur.pk, exc,
        )
        return

    reste_distant_par_id = {e['id']: Decimal(e['reste_a_rembourser']) for e in distants}

    for depense in a_verifier:
        reste_distant = reste_distant_par_id.get(depense.reference_dams_agro)
        if reste_distant is None:
            continue

        ecart = depense.reste_a_rembourser_champ - reste_distant
        if ecart > 0:
            RemboursementChamp.objects.create(depense=depense, montant=ecart)


def lister_engagements_champ(superviseur, limite=20):
    """
    Avances/dépenses champ de CE superviseur, les plus récentes en premier —
    source de vérité locale (Depense + RemboursementChamp). Pas d'appel API
    ici : lecture seule, rapide, indépendante de la disponibilité de
    dams_agro (voir finance:mes_engagements_champ pour la synchronisation,
    déclenchée séparément à l'entrée sur cette page).
    """
    return list(
        Depense.objects.filter(
            effectue_par=superviseur,
            categorie__in=CATEGORIES_ENGAGEMENT_CHAMP,
        )
        .prefetch_related('remboursements_champ')
        .order_by('-date_depense')[:limite]
    )
