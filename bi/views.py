import calendar
import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Max, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from bi import constants
from bi.models import (
    AjustementPrixAchat,
    FctStockAgent,
    VwAnalyseStock,
    VwDepensesCategorie,
    VwMargeFournisseur,
    VwPerformanceAgent,
    VwPerformanceAgentSemaine,
    VwPerformanceSuperviseur,
    VwPerformanceSuperviseurSemaine,
    VwRentabiliteGlobale,
    VwRentabiliteJournaliere,
    VwRentabiliteProduit,
    VwVentesAgentProduit,
)
from core.models import Agent, RegleSalaire
from paie.services.salaire_calculator import CalculatorSalaire


def _est_utilisateur_autorise(user):
    return (
        user.is_authenticated
        and hasattr(user, 'agent')
        and user.agent.est_direction
    )


bi_access_required = user_passes_test(_est_utilisateur_autorise, login_url="login")

MOIS_FR = [
    "",
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def _dernier_mois_disponible():
    """Mois par défaut quand aucun filtre n'est choisi en GET : le dernier mois avec des
    données dans vw_rentabilite_globale (source mensuelle centrale), pour ne pas submerger les
    pages avec toutes les périodes cumulées par défaut. Repli sur le mois calendaire courant si
    la vue est vide (aucune donnée du tout)."""
    dernier = VwRentabiliteGlobale.objects.aggregate(Max("mois"))["mois__max"]
    if dernier:
        return dernier.year, dernier.month
    aujourdhui = timezone.now().date()
    return aujourdhui.year, aujourdhui.month


def _parse_periode(request):
    """Lit ?annee=&mois= depuis GET. En l'absence des deux (et sans ?toutes_periodes=1), retombe
    sur le dernier mois disponible (cf. _dernier_mois_disponible) plutôt que "Toutes périodes" —
    décision produit : chaque page affiche le dernier mois par défaut pour rester lisible.
    vw_performance_superviseur reste à grain all-time (pas de dimension mois en base) : annee/mois
    y sont propagés dans le sélecteur/les liens pour la cohérence de navigation mais ne filtrent
    pas cette vue. Toutes les autres vues (vw_rentabilite_globale, vw_rentabilite_produit,
    vw_marge_fournisseur, vw_depenses_categorie, vw_performance_agent) ont une colonne `mois`."""
    if request.GET.get("toutes_periodes"):
        return None, None, "Toutes périodes"

    annee_raw = request.GET.get("annee")
    mois_raw = request.GET.get("mois")
    try:
        annee = int(annee_raw) if annee_raw else None
    except ValueError:
        annee = None
    try:
        mois = int(mois_raw) if mois_raw else None
    except ValueError:
        mois = None

    if not annee and not mois:
        annee, mois = _dernier_mois_disponible()

    if annee and mois:
        libelle = f"{MOIS_FR[mois]} {annee}"
    elif annee:
        libelle = str(annee)
    else:
        libelle = "Toutes périodes"
    return annee, mois, libelle


def _base_context(request, slug, titre):
    annee, mois, periode_libelle = _parse_periode(request)
    onglets = [
        {"slug": s, "titre": t, "url": reverse(f"bi:{s}")} for s, t in constants.DASHBOARDS
    ]
    return {
        "dashboards": onglets,
        "dashboard_slug": slug,
        "dashboard_titre": titre,
        "annee": annee,
        "mois": mois,
        "periode_libelle": periode_libelle,
        "mois_options": list(enumerate(MOIS_FR))[1:],
    }


def _chart_json(data):
    return json.dumps(data, cls=DjangoJSONEncoder)


def _agreger_rentabilite(lignes):
    """Agrège plusieurs lignes mensuelles de vw_rentabilite_globale en une seule (somme des
    montants, pourcentages recalculés sur les totaux) — utilisé par le filtre temporel custom
    du Dashboard Santé Globale, qui peut couvrir plusieurs mois."""
    ca = sum(l.ca for l in lignes)
    cout_achat = sum(l.cout_achat for l in lignes)
    marge_brute = sum(l.marge_brute for l in lignes)
    cout_salaires = sum(l.cout_salaires for l in lignes)
    cout_depenses = sum(l.cout_depenses for l in lignes)
    rentabilite_nette = sum(l.rentabilite_nette for l in lignes)
    return SimpleNamespace(
        ca=ca,
        cout_achat=cout_achat,
        marge_brute=marge_brute,
        marge_pct=(marge_brute / ca * 100) if ca else None,
        cout_salaires=cout_salaires,
        salaires_pct=(cout_salaires / ca * 100) if ca else None,
        cout_depenses=cout_depenses,
        depenses_pct=(cout_depenses / ca * 100) if ca else None,
        rentabilite_nette=rentabilite_nette,
        rentabilite_nette_pct=(rentabilite_nette / ca * 100) if ca else None,
    )


@bi_access_required
def dashboard_sante(request):
    titre = dict(constants.DASHBOARDS)["sante"]
    context = _base_context(request, "sante", titre)
    annee, mois = context["annee"], context["mois"]

    # Filtre temporel custom (date_debut/date_fin), propre au Dashboard Santé Globale — permet
    # une plage à cheval sur plusieurs mois, en plus du sélecteur année/mois du base_dashboard.
    date_debut = parse_date(request.GET.get("date_debut") or "")
    date_fin = parse_date(request.GET.get("date_fin") or "")
    periode_custom = bool(date_debut and date_fin)
    context.update({"date_debut": date_debut, "date_fin": date_fin})

    qs = VwRentabiliteGlobale.objects.order_by("mois")
    if periode_custom:
        qs = qs.filter(mois__gte=date_debut, mois__lte=date_fin)
        context["periode_libelle"] = f"{date_debut:%d/%m/%Y} – {date_fin:%d/%m/%Y}"
    else:
        if annee:
            qs = qs.filter(mois__year=annee)
        if mois:
            qs = qs.filter(mois__month=mois)
    lignes = list(qs)

    if not lignes:
        context["est_vide"] = True
        return render(request, "bi/dashboard_sante.html", context)

    courante = _agreger_rentabilite(lignes) if periode_custom else lignes[-1]

    # Comparaison de la marge brute du mois/de la période sélectionnée (courante.marge_brute —
    # la valeur réellement affichée dans le KPI, agrégée si filtre custom multi-mois) face au
    # mois qui précède immédiatement cette sélection dans les données (pas "aujourd'hui - 1
    # mois" : le mois de référence suit le filtre actif, par défaut le dernier mois disponible).
    mois_reference = lignes[-1].mois
    mois_precedent = (
        VwRentabiliteGlobale.objects.filter(mois__lt=mois_reference)
        .order_by("-mois")
        .first()
    )
    comparaison_marge_brute = None
    if mois_precedent:
        marge_brute_precedente = mois_precedent.marge_brute
        delta = courante.marge_brute - marge_brute_precedente
        comparaison_marge_brute = {
            "mois_precedent_libelle": f"{MOIS_FR[mois_precedent.mois.month]} {mois_precedent.mois.year}",
            "delta": delta,
            "delta_pct": (delta / marge_brute_precedente * 100) if marge_brute_precedente else None,
        }
    context["comparaison_marge_brute"] = comparaison_marge_brute
    # Priorité de cette phase (23/07/2026) : déterminer la marge BRUTE (a-t-on de la marge sur
    # nos ventes ?), la marge nette (qui englobe salaires + dépenses ROT) est une vue
    # complémentaire, secondaire pour l'instant — d'où les deux groupes distincts.
    kpis_marge_brute = [
        {
            "code": "KPI-001",
            "label": "Chiffre d'affaires",
            "valeur": courante.ca,
            "unite": "FCFA",
            "statut": constants.NEUTRE,
        },
        {
            "code": "KPI-002",
            "label": "Coût d'achat",
            "valeur": courante.cout_achat,
            "unite": "FCFA",
            "statut": constants.NEUTRE,
        },
        {
            "code": "KPI-003",
            "label": "Marge brute",
            "valeur": courante.marge_brute,
            "unite": "FCFA",
            "statut": (
                constants.VERT if courante.marge_brute >= constants.MARGE_BRUTE_CIBLE else constants.JAUNE
            ),
        },
        {
            "code": "KPI-004",
            "label": "Marge brute %",
            "valeur": courante.marge_pct,
            "unite": "%",
            "statut": constants.statut_marge_pct(courante.marge_pct),
        },
    ]
    kpis_marge_nette = [
        {
            "code": "KPI-007",
            "label": "Dépenses ",
            "valeur": courante.cout_depenses,
            "unite": "FCFA",
            "statut": constants.NEUTRE,
        },
        {
            "code": "KPI-005",
            "label": "Coût salaires",
            "valeur": courante.cout_salaires,
            "unite": "FCFA",
            "statut": constants.NEUTRE,
        },
        {
            "code": "KPI-009",
            "label": "Marge nette",
            "valeur": courante.rentabilite_nette,
            "unite": "FCFA",
            "statut": constants.statut_rentabilite_nette(courante.rentabilite_nette),
        },
        {
            "code": "KPI-010",
            "label": "Marge nette %",
            "valeur": courante.rentabilite_nette_pct,
            "unite": "%",
            "statut": constants.NEUTRE,
        },
    ]

    # Graphique en journalier quand un mois précis (ou une plage custom) est filtré : le grain
    # mensuel de vw_rentabilite_globale réduirait sinon la série à un seul point par mois. En
    # "Toutes périodes", on garde la tendance mensuelle multi-mois.
    chart_est_journalier = periode_custom or bool(annee and mois)
    if periode_custom:
        jours_qs = VwRentabiliteJournaliere.objects.filter(
            jour__gte=date_debut, jour__lte=date_fin
        ).order_by("jour")
    elif chart_est_journalier:
        jours_qs = VwRentabiliteJournaliere.objects.filter(
            jour__year=annee, jour__month=mois
        ).order_by("jour")
    if chart_est_journalier:
        jours = list(jours_qs)
        chart_data = _chart_json(
            {
                "labels": [j.jour.strftime("%d/%m") for j in jours],
                "ca": [j.ca for j in jours],
                "cout_depenses": [j.cout_depenses for j in jours],
                "marge_brute": [j.marge_brute for j in jours],
            }
        )
    else:
        chart_data = _chart_json(
            {
                "labels": [f"{ligne.mois.month:02d}/{ligne.mois.year}" for ligne in lignes],
                "ca": [ligne.ca for ligne in lignes],
                "cout_depenses": [ligne.cout_depenses for ligne in lignes],
                "marge_brute": [ligne.marge_brute for ligne in lignes],
            }
        )

    # ---- Marge brute des 6 derniers mois (mdmaiga, 19/08/2026) — fixe, indépendant du filtre
    # de période actif : sert de repère de tendance long terme même quand la sélection en cours
    # porte sur un seul mois ou une plage custom.
    semestre = list(VwRentabiliteGlobale.objects.order_by("-mois")[:6])
    semestre.reverse()
    chart_semestre = _chart_json(
        {
            "labels": [f"{MOIS_FR[l.mois.month]} {l.mois.year}" for l in semestre],
            "marge_brute": [l.marge_brute for l in semestre],
        }
    )

    # ---- Top 10 agents (kg vendus) et top 10 produits (CA), sur le mois de référence de la
    # période sélectionnée (mois_reference, déjà calculé ci-dessus pour la comparaison M-1) —
    # reste un mois calendaire unique même en filtre custom multi-mois, pour ne pas avoir à
    # sommer des grains différents (agent x mois, produit x mois) sur une plage arbitraire.
    top_agents_kg = list(
        VwPerformanceAgent.objects.filter(mois=mois_reference).order_by("-kg_vendus")[:10]
    )
    top_produits_ca = list(
        VwRentabiliteProduit.objects.filter(mois=mois_reference).order_by("-ca")[:10]
    )
    # Top 10 agents par marge brute (mdmaiga, 19/08/2026, révisé le même jour — CA remplacé par
    # marge brute, plus utile) : "les gros vendeurs (kg) ne sont pas forcément ceux qui
    # rapportent le plus" — pertinent à côté du top kg vendus pour ce constat. `marge` existe
    # directement sur VwPerformanceAgent (grain agent x mois, déjà utilisée par dashboard_agents
    # pour la colonne Rentabilité côté brut) : pas besoin d'agréger depuis un autre mart.
    top_agents_marge = list(
        VwPerformanceAgent.objects.filter(mois=mois_reference).order_by("-marge")[:10]
    )
    top_mois_libelle = f"{MOIS_FR[mois_reference.month]} {mois_reference.year}"

    context.update(
        {
            "kpis_marge_brute": kpis_marge_brute,
            "kpis_marge_nette": kpis_marge_nette,
            "chart_data": chart_data,
            "chart_est_journalier": chart_est_journalier,
            "chart_semestre": chart_semestre,
            "top_agents_kg": top_agents_kg,
            "top_agents_marge": top_agents_marge,
            "top_produits_ca": top_produits_ca,
            "top_mois_libelle": top_mois_libelle,
        }
    )
    return render(request, "bi/dashboard_sante.html", context)


@bi_access_required
def dashboard_produits(request):
    titre = dict(constants.DASHBOARDS)["produits"]
    context = _base_context(request, "produits", titre)
    annee, mois = context["annee"], context["mois"]

    qs = VwRentabiliteProduit.objects.order_by("-marge")
    if annee:
        qs = qs.filter(mois__year=annee)
    if mois:
        qs = qs.filter(mois__month=mois)
    produits = list(qs)
    if not produits:
        context["est_vide"] = True
        return render(request, "bi/dashboard_produits.html", context)

    for p in produits:
        p.statut = constants.statut_marge_produit(p.marge, p.marge_pct)

    nb_deficitaires = qs.filter(marge__lt=0).values("produit_id").distinct().count()

    chart_data = _chart_json(
        {
            "labels": [f"{p.produit_nom} ({p.mois.month:02d}/{p.mois.year})" for p in produits],
            "marge": [p.marge for p in produits],
        }
    )

    context.update(
        {
            "produits": produits,
            "nb_deficitaires": nb_deficitaires,
            "chart_data": chart_data,
        }
    )
    return render(request, "bi/dashboard_produits.html", context)


def _mois_precedent(annee, mois):
    if mois == 1:
        return annee - 1, 12
    return annee, mois - 1


@bi_access_required
def dashboard_agents(request):
    """Dashboard Agents : bloc superviseurs/équipes (KPI-201 à 206, tri par kilo vendu — priorité
    produit du 24/07/2026, cf. chef_projet/BILAN_LIVRAISON_VS_VISION.md) suivi du détail agents
    vs objectif 50 kg/jour (KPI-301 à 306). Bascule semaine/mois (S-702, 24/07/2026) : pas de
    "Toutes périodes" ici (UX jugée illisible sur ce dashboard, cf. filtre_periode surchargé
    dans dashboard_agents.html) — toujours une période concrète, semaine ISO ou mois calendaire.
    """
    titre = dict(constants.DASHBOARDS)["agents"]
    context = _base_context(request, "agents", titre)

    granularite = request.GET.get("granularite")
    if granularite not in ("semaine", "mois"):
        granularite = "mois"
    context["granularite"] = granularite

    if granularite == "semaine":
        semaines_disponibles = list(
            VwPerformanceAgentSemaine.objects.order_by("-semaine")
            .values_list("semaine", flat=True)
            .distinct()[:12]
        )
        semaine_demandee = parse_date(request.GET.get("semaine") or "")
        semaine_selectionnee = (
            semaine_demandee
            if semaine_demandee in semaines_disponibles
            else (semaines_disponibles[0] if semaines_disponibles else None)
        )
        context.update(
            {
                "semaines_disponibles": semaines_disponibles,
                "semaine_selectionnee": semaine_selectionnee,
            }
        )
        if semaine_selectionnee:
            context["periode_libelle"] = (
                f"Semaine du {semaine_selectionnee:%d/%m/%Y} "
                f"au {(semaine_selectionnee + timedelta(days=6)):%d/%m/%Y}"
            )
            superviseurs_qs = VwPerformanceSuperviseurSemaine.objects.filter(
                semaine=semaine_selectionnee
            ).order_by("-kg_vendus")
            agents_qs = VwPerformanceAgentSemaine.objects.filter(
                semaine=semaine_selectionnee
            ).order_by("-kg_par_jour")
            semaine_precedente = semaine_selectionnee - timedelta(days=7)
            kg_vendus_precedents = dict(
                VwPerformanceSuperviseurSemaine.objects.filter(
                    semaine=semaine_precedente
                ).values_list("superviseur_id", "kg_vendus")
            )
            kg_vendus_precedents_agent = dict(
                VwPerformanceAgentSemaine.objects.filter(
                    semaine=semaine_precedente
                ).values_list("agent_id", "kg_vendus")
            )
            periode_precedente_libelle = f"la semaine du {semaine_precedente:%d/%m/%Y}"
        else:
            superviseurs_qs = VwPerformanceSuperviseurSemaine.objects.none()
            agents_qs = VwPerformanceAgentSemaine.objects.none()
            kg_vendus_precedents = {}
            kg_vendus_precedents_agent = {}
            periode_precedente_libelle = None
    else:
        annee, mois = context["annee"], context["mois"]
        if not annee or not mois:
            annee, mois = _dernier_mois_disponible()
            context["annee"], context["mois"] = annee, mois
        context["periode_libelle"] = f"{MOIS_FR[mois]} {annee}"

        superviseurs_qs = VwPerformanceSuperviseur.objects.filter(
            mois__year=annee, mois__month=mois
        ).order_by("-kg_vendus")
        agents_qs = VwPerformanceAgent.objects.filter(
            mois__year=annee, mois__month=mois
        ).order_by("-kg_par_jour")
        annee_prec, mois_prec = _mois_precedent(annee, mois)
        kg_vendus_precedents = dict(
            VwPerformanceSuperviseur.objects.filter(
                mois__year=annee_prec, mois__month=mois_prec
            ).values_list("superviseur_id", "kg_vendus")
        )
        kg_vendus_precedents_agent = dict(
            VwPerformanceAgent.objects.filter(
                mois__year=annee_prec, mois__month=mois_prec
            ).values_list("agent_id", "kg_vendus")
        )
        periode_precedente_libelle = f"{MOIS_FR[mois_prec]} {annee_prec}"

    if granularite == "semaine":
        jours_ouvres_periode = (
            _jours_ouvres_dans_periode(semaine_selectionnee, semaine_selectionnee + timedelta(days=6))
            if semaine_selectionnee
            else 0
        )
    else:
        jours_ouvres_periode = _jours_ouvres_dans_periode(
            date(annee, mois, 1), date(annee, mois, calendar.monthrange(annee, mois)[1])
        )

    type_agent_filtre = request.GET.get("type_agent")
    if type_agent_filtre:
        agents_qs = agents_qs.filter(type_agent=type_agent_filtre)

    superviseur_filtre = request.GET.get("superviseur")
    if superviseur_filtre:
        agents_qs = agents_qs.filter(superviseur_id=superviseur_filtre)

    superviseurs = list(superviseurs_qs)
    agents = list(agents_qs)

    if not superviseurs and not agents:
        context["est_vide"] = True
        return render(request, "bi/dashboard_agents.html", context)

    for s in superviseurs:
        kg_precedent = kg_vendus_precedents.get(s.superviseur_id)
        s.kg_vendus_precedent = kg_precedent
        s.kg_vendus_delta = (s.kg_vendus - kg_precedent) if kg_precedent is not None else None
        # Kg/jour moyen par agent de l'équipe vs objectif individuel 50 kg/jour — même formule
        # que dashboard_superviseur_detail (kg_par_jour_equipe / nb_agents_actifs), pour que le
        # superviseur voie d'un coup d'œil si son équipe pousse vers le seuil individuel.
        s.objectif_kg_jour_equipe = s.nb_agents_actifs * 50
        s.kg_par_jour_equipe = (
            (s.kg_vendus / jours_ouvres_periode) if jours_ouvres_periode else Decimal("0.00")
        )
        s.kg_par_jour_moyen_agent = (
            (s.kg_par_jour_equipe / s.nb_agents_actifs) if s.nb_agents_actifs else Decimal("0.00")
        )
        if not s.nb_agents_actifs:
            statut_equipe = "sous_objectif"
        elif s.kg_par_jour_moyen_agent >= 50:
            statut_equipe = "atteint"
        elif s.kg_par_jour_moyen_agent >= 40:
            statut_equipe = "proche"
        else:
            statut_equipe = "sous_objectif"
        s.statut_couleur = constants.statut_objectif_agent(statut_equipe)
        s.statut_label = constants.STATUT_OBJECTIF_LABELS.get(statut_equipe, "—")

    for a in agents:
        a.statut_couleur = constants.statut_objectif_agent(a.statut_objectif_50kg)
        a.statut_label = constants.STATUT_OBJECTIF_LABELS.get(a.statut_objectif_50kg, "—")
        # Jours actifs/ouvrés combinés en une seule info ("15/26") — les deux colonnes
        # séparées prenaient de la place pour peu de valeur de lecture (mdmaiga, 18/08/2026).
        a.jours_label = (
            f"{a.jours_actifs}/{a.jours_ouvres}" if a.jours_ouvres else "—"
        )
        kg_precedent = kg_vendus_precedents_agent.get(a.agent_id)
        a.kg_vendus_precedent = kg_precedent
        a.kg_vendus_delta = (a.kg_vendus - kg_precedent) if kg_precedent is not None else None
        # Rentabilité : réintégrée le 18/08/2026 (retrait précédent = mauvaise lecture de
        # la demande de mdmaiga, la colonne reste utile) — grain semaine
        # (VwPerformanceAgentSemaine) n'a pas d'incentive (fct_salaires est mensuel, cf.
        # commentaire dbt), rentabilité affichée = marge brute dans ce cas.
        a.rentabilite_affichee = getattr(a, "rentabilite_agent", a.marge)
        a.statut_rentabilite = constants.statut_rentabilite_agent(a.rentabilite_affichee)

    # Tri du tableau "Agent / Superviseur / ..." (demande mdmaiga, 19/08/2026) : toutes les
    # colonnes triables via les en-têtes cliquables (?tri=...&ordre=asc|desc), pas seulement
    # kg vendus/delta/rentabilité initialement suggérés. Tri en Python (pas en SQL) car
    # kg_vendus_delta/rentabilite_affichee/statut_couleur sont calculés ci-dessus, après la
    # requête. Les valeurs manquantes (ex. delta sans période précédente) sont toujours
    # reléguées en fin de liste, quel que soit le sens de tri choisi.
    TRI_AGENTS_CLES = {
        "nom": lambda a: a.nom_complet,
        "superviseur": lambda a: a.superviseur_nom,
        "jours_actifs": lambda a: a.jours_actifs,
        "kg_vendus": lambda a: a.kg_vendus,
        "delta": lambda a: a.kg_vendus_delta,
        "kg_par_jour": lambda a: a.kg_par_jour,
        "rentabilite": lambda a: a.rentabilite_affichee,
    }
    tri_agents = request.GET.get("tri")
    if tri_agents not in TRI_AGENTS_CLES:
        tri_agents = "kg_par_jour"
    ordre_agents = request.GET.get("ordre")
    if ordre_agents not in ("asc", "desc"):
        ordre_agents = "desc"
    cle_tri = TRI_AGENTS_CLES[tri_agents]
    agents_avec_valeur = [a for a in agents if cle_tri(a) is not None]
    agents_sans_valeur = [a for a in agents if cle_tri(a) is None]
    agents_avec_valeur.sort(key=cle_tri, reverse=(ordre_agents == "desc"))
    agents = agents_avec_valeur + agents_sans_valeur

    querydict_sans_tri = request.GET.copy()
    querydict_sans_tri.pop("tri", None)
    querydict_sans_tri.pop("ordre", None)
    base_querystring_tri = querydict_sans_tri.urlencode()

    superviseurs_chart = _chart_json(
        {
            "labels": [s.superviseur_nom for s in superviseurs],
            "kg_vendus": [s.kg_vendus for s in superviseurs],
        }
    )
    chart_data = _chart_json(
        {
            "labels": [a.nom_complet for a in agents],
            "agent_ids": [a.agent_id for a in agents],
            "kg_par_jour": [a.kg_par_jour for a in agents],
            "objectif": [50 for _ in agents],
        }
    )

    context.update(
        {
            "superviseurs": superviseurs,
            "superviseurs_chart": superviseurs_chart,
            "periode_precedente_libelle": periode_precedente_libelle,
            "agents": agents,
            "chart_data": chart_data,
            "superviseur_filtre": int(superviseur_filtre) if superviseur_filtre else None,
            "type_agent_filtre": type_agent_filtre or None,
            "type_agent_options": constants.TYPE_AGENT_CHOICES,
            "jours_ouvres_periode": jours_ouvres_periode,
            "tri_agents": tri_agents,
            "ordre_agents": ordre_agents,
            "base_querystring_tri": base_querystring_tri,
        }
    )
    return render(request, "bi/dashboard_agents.html", context)


def _mois_moins_n(annee, mois, n):
    """Retourne (annee, mois) n mois avant (annee, mois) — arithmétique pure, même esprit que
    _mois_precedent (pas de dépendance date lib supplémentaire)."""
    total = (annee * 12 + (mois - 1)) - n
    return total // 12, total % 12 + 1


NB_PERIODES_TENDANCE = 6


@bi_access_required
def dashboard_agent_detail(request, agent_id):
    """Sprint-11 (18/08/2026, étendu le même jour). Fiche détail d'un agent, accessible depuis
    une ligne du tableau de dashboard_agents. Trois blocs demandés par mdmaiga :
    - Atteinte des objectifs : tendance sur les 6 dernières périodes, bascule mois/semaine
      (comme dashboard_agents — la réunion hebdomadaire du lundi porte sur le progrès semaine
      par semaine, pas seulement mensuel) + comparaison n vs n-1 (delta kg vendus vs période
      précédente, même pattern que le delta superviseur de dashboard_agents). 50 kg/jour (BI) et
      750 kg/mois (seuil du salaire fixe, paie). Pas de nouvel "objectif configurable" : décision
      actée (docs/sprints/sprint-11.md).
    - Produits vendus : VwVentesAgentProduit filtrée sur le mois courant (pas de grain
      hebdomadaire pour ce bloc), triée par kg vendus décroissant — "type" = nom du produit,
      clarifié par mdmaiga au cadrage du sprint.
    - Stock en main : FctStockAgent, snapshot batch (pas de filtre de période), décision produit
      actée (séparation OLTP/BI).
    Incentive (corrigé le 18/08/2026, réaligné le 21/08/2026 après l'introduction de
    Produit.taux_incentive — voir paie/APP_PAIE.md et paie/services/salaire_calculator.py).
    Pour un agent terrain, incentive_projetee appelle désormais directement
    CalculatorSalaire.calcul_salaire_mamy(agent, date_debut, date_fin) pour chaque période de la
    tendance, au lieu de réimplémenter la formule (kg_vendus x incentive_par_kg) : cette
    reimplémentation ignorait les taux dédiés par produit (concombre, huile, spaghetti...) ajoutés
    au sprint du 21/08, elle sortait donc du "reproduit exactement calcul_salaire_mamy" annoncé
    plus haut par cette même note. Le calcul reste EN DIRECT, il ne lit jamais le modèle Salaire ;
    aucune génération manuelle n'est requise pour connaître un salaire au quotidien. Fonctionne à
    toute granularité (mois ou semaine) puisqu'il ne dépend pas de fct_salaires. Le modèle
    Salaire/SalaireGenerationService existe toujours mais sert un usage séparé et optionnel
    (verrouiller/archiver un montant, ex. avant versement) — quand une ligne existe pour la
    période (VwPerformanceAgent.incentive, mois uniquement), elle est affichée en complément pour
    comparaison, pas comme LA valeur de référence. Masquable comme CA/marge
    (bi-toggle-donnees-sensibles).
    Pas de "Toutes périodes" ici (cohérent avec dashboard_agents, cf. son commentaire d'en-tête).
    """
    agent = get_object_or_404(
        Agent.objects.select_related("user", "superviseur__user"), pk=agent_id
    )
    context = _base_context(request, "agents", f"Détail agent — {agent.full_name}")

    granularite = request.GET.get("granularite")
    if granularite not in ("semaine", "mois"):
        granularite = "mois"
    context["granularite"] = granularite

    taux_incentive = (
        RegleSalaire.objects.filter(type_agent="terrain", actif=True)
        .values_list("incentive_par_kg", flat=True)
        .first()
    ) or Decimal("0.00")

    annee, mois = context["annee"], context["mois"]
    if not annee or not mois:
        annee, mois = _dernier_mois_disponible()
        context["annee"], context["mois"] = annee, mois

    if granularite == "semaine":
        Modele = VwPerformanceAgentSemaine
        champ_periode = "semaine"
        semaines_disponibles = list(
            VwPerformanceAgentSemaine.objects.filter(agent_id=agent_id)
            .order_by("-semaine")
            .values_list("semaine", flat=True)
            .distinct()[:26]
        )
        semaine_demandee = parse_date(request.GET.get("semaine") or "")
        periode_courante_val = (
            semaine_demandee
            if semaine_demandee in semaines_disponibles
            else (semaines_disponibles[0] if semaines_disponibles else None)
        )
        context["semaines_disponibles"] = semaines_disponibles
        context["semaine_selectionnee"] = periode_courante_val
        if periode_courante_val:
            context["periode_libelle"] = (
                f"Semaine du {periode_courante_val:%d/%m/%Y} au "
                f"{(periode_courante_val + timedelta(days=6)):%d/%m/%Y}"
            )
            debut_tendance = periode_courante_val - timedelta(weeks=NB_PERIODES_TENDANCE - 1)
            tendance_qs = Modele.objects.filter(
                agent_id=agent_id, semaine__gte=debut_tendance, semaine__lte=periode_courante_val
            ).order_by("semaine")
            periode_precedente_val = periode_courante_val - timedelta(weeks=1)
            periode_precedente_libelle = f"la semaine du {periode_precedente_val:%d/%m/%Y}"
        else:
            tendance_qs = Modele.objects.none()
            periode_precedente_val = None
            periode_precedente_libelle = None
    else:
        Modele = VwPerformanceAgent
        champ_periode = "mois"
        context["periode_libelle"] = f"{MOIS_FR[mois]} {annee}"
        periode_courante_val = date(annee, mois, 1)
        annee_debut, mois_debut = _mois_moins_n(annee, mois, NB_PERIODES_TENDANCE - 1)
        tendance_qs = Modele.objects.filter(
            agent_id=agent_id,
            mois__gte=date(annee_debut, mois_debut, 1),
            mois__lte=periode_courante_val,
        ).order_by("mois")
        annee_prec, mois_prec = _mois_precedent(annee, mois)
        periode_precedente_val = date(annee_prec, mois_prec, 1)
        periode_precedente_libelle = f"{MOIS_FR[mois_prec]} {annee_prec}"

    def _incentive_periode(periode):
        # Agent terrain : appel direct à calcul_salaire_mamy (source de vérité unique, inclut
        # les taux dédiés par produit — Produit.taux_incentive). Les autres types d'agent
        # gardent l'ancienne approximation kg x taux global, hors périmètre de ce calculateur.
        if agent.type_agent != "terrain":
            return (getattr(periode, "kg_vendus", None) or Decimal("0.00")) * taux_incentive
        if granularite == "semaine":
            date_debut = periode
            date_fin = periode + timedelta(days=6)
        else:
            date_debut = periode
            date_fin = date(periode.year, periode.month, calendar.monthrange(periode.year, periode.month)[1])
        return CalculatorSalaire.calcul_salaire_mamy(agent, date_debut, date_fin)["incentive"]

    tendance = list(tendance_qs)
    for t in tendance:
        t.periode = getattr(t, champ_periode)
        t.statut_couleur = constants.statut_objectif_agent(t.statut_objectif_50kg)
        t.statut_label = constants.STATUT_OBJECTIF_LABELS.get(t.statut_objectif_50kg, "—")
        # Seuil salaire fixe (paie/services/salaire_calculator.py, kilo net des pertes depuis
        # le sprint-10 — kg_vendus ici est déjà net, corrigé au sprint-11 pour la cohérence).
        t.statut_750kg = "atteint" if t.kg_vendus >= 750 else "sous_objectif"
        t.incentive_projetee = _incentive_periode(t.periode)

    periode_courante = next((t for t in tendance if t.periode == periode_courante_val), None)
    periode_precedente = next((t for t in tendance if t.periode == periode_precedente_val), None)
    if periode_precedente is None and periode_precedente_val is not None:
        # Fenêtre de tendance trop courte pour couvrir n-1 (ne devrait pas arriver avec
        # NB_PERIODES_TENDANCE >= 2, gardé par robustesse) — requête dédiée.
        periode_precedente = Modele.objects.filter(
            agent_id=agent_id, **{champ_periode: periode_precedente_val}
        ).first()
        if periode_precedente:
            periode_precedente.periode = periode_precedente_val
            periode_precedente.incentive_projetee = _incentive_periode(periode_precedente_val)

    delta_kg_vendus = None
    delta_kg_vendus_pct = None
    if periode_courante and periode_precedente:
        delta_kg_vendus = periode_courante.kg_vendus - periode_precedente.kg_vendus
        if periode_precedente.kg_vendus:
            delta_kg_vendus_pct = float(
                delta_kg_vendus / periode_precedente.kg_vendus * 100
            )

    produits = list(
        VwVentesAgentProduit.objects.filter(
            agent_id=agent_id, mois=date(annee, mois, 1)
        ).order_by("-kg_vendus")
    )

    stock = list(FctStockAgent.objects.filter(agent_id=agent_id).order_by("-stock_restant_kg"))
    stock_total_kg = sum((s.stock_restant_kg for s in stock), Decimal("0.00"))

    if not tendance and not produits and not stock:
        context["est_vide"] = True
        context["agent"] = agent
        return render(request, "bi/dashboard_agent_detail.html", context)

    tendance_chart = _chart_json(
        {
            "labels": (
                [f"S{t.periode:%W} ({t.periode:%d/%m})" for t in tendance]
                if granularite == "semaine"
                else [f"{MOIS_FR[t.periode.month][:3]} {t.periode.year}" for t in tendance]
            ),
            "kg_par_jour": [float(t.kg_par_jour or 0) for t in tendance],
            "incentive_projetee": [float(t.incentive_projetee or 0) for t in tendance],
            "objectif": [50 for _ in tendance],
        }
    )

    context.update(
        {
            "agent": agent,
            "tendance": tendance,
            "tendance_chart": tendance_chart,
            "periode_courante": periode_courante,
            "periode_precedente_libelle": periode_precedente_libelle,
            "delta_kg_vendus": delta_kg_vendus,
            "delta_kg_vendus_pct": delta_kg_vendus_pct,
            "taux_incentive": taux_incentive,
            "produits": produits,
            "stock": stock,
            "stock_total_kg": stock_total_kg,
        }
    )
    return render(request, "bi/dashboard_agent_detail.html", context)


def _jours_ouvres_dans_periode(date_debut, date_fin):
    """Compte les jours lundi-samedi (dimanche exclu) entre deux dates incluses — même
    convention que les marts dbt (vw_performance_agent(_semaine).sql, cf. utils/calendrier.py
    pour la convention "lundi-samedi" ailleurs dans le repo)."""
    jours = 0
    courant = date_debut
    while courant <= date_fin:
        if courant.weekday() != 6:
            jours += 1
        courant += timedelta(days=1)
    return jours


@bi_access_required
def dashboard_superviseur_detail(request, superviseur_id):
    """Sprint-11 (18/08/2026, cadré avec mdmaiga avant codage). Fiche détail d'un superviseur —
    pendant de dashboard_agent_detail à l'échelle d'une équipe. Décisions actées :
    - Bascule Mois/Semaine (comme le reste de ce dashboard), avec n vs n-1.
    - Objectif équipe = somme des 50 kg/jour de chaque agent actif (nb_agents_actifs x 50),
      comparé au kg/jour réel de l'équipe — pas un seuil inventé, dérivé de l'objectif agent
      existant. Même statut vert/jaune/rouge que le niveau agent (>=50 atteint, >=40 proche).
    - CA moyen par agent vs cible (bi/constants.py::CA_MOYEN_AGENT_CIBLE, existait déjà mais
      n'était branché nulle part) — calculé ici (ca / nb_agents_actifs) plutôt que lu depuis
      VwPerformanceSuperviseur.ca_moyen_par_agent, qui n'existe qu'au grain mensuel : garantit
      la même formule aux deux granularités.
    - Coût/rentabilité d'équipe (cout_equipe, rentabilite_nette) : mois uniquement, ces montants
      n'existent pas au grain semaine (salaires mensuels par nature, cf. commentaire dbt de
      vw_performance_superviseur_semaine.sql).
    - Stock en main et produits vendus agrégés sur l'ÉQUIPE ACTUELLE (core.Agent.superviseur_id,
      hiérarchie actuelle) plutôt que sur le superviseur_id embarqué dans FctStockAgent (hiérarchie
      au moment de la distribution — cf. distinction déjà documentée pour fct_ventes/fct_salaires)
      : cohérence garantie avec la liste d'agents affichée, filtrée elle aussi sur la hiérarchie
      actuelle (VwPerformanceAgent.superviseur_id).
    Révision du 18/08/2026 (retours mdmaiga après la première version) :
    - Retrait du KPI "Coût équipe" (gardé Kg vendus/Objectif équipe/CA moyen/Rentabilité nette
      sur la même ligne).
    - Ordre de page imposé : KPIs → tableau produits → tableau agents → graphes tendance →
      stock en main.
    - Comparaison n vs n-1 ajoutée aussi sur le tableau produits ET le tableau agents (pas
      seulement le KPI global).
    - Filtre produit (GET ?produit=<id>) étendu : influence désormais aussi le tableau agents
      (kg vendus/delta deviennent spécifiques à ce produit) — mois uniquement, pas de grain
      hebdomadaire pour vw_ventes_agent_produit.
    - Graphique tendance unifié (plus de mini-graphique séparé) : barres = kg vendus équipe,
      courbes = kg vendus par produit (une couleur par produit, top 5 si pas de filtre, sinon
      uniquement le produit filtré) — mois uniquement, l'axe produit reste vide en vue semaine.
    """
    superviseur = get_object_or_404(
        Agent.objects.select_related("user"), pk=superviseur_id, type_agent="entrepot"
    )
    context = _base_context(request, "agents", f"Détail équipe — {superviseur.full_name}")

    granularite = request.GET.get("granularite")
    if granularite not in ("semaine", "mois"):
        granularite = "mois"
    context["granularite"] = granularite

    annee, mois = context["annee"], context["mois"]
    if not annee or not mois:
        annee, mois = _dernier_mois_disponible()
        context["annee"], context["mois"] = annee, mois

    types_cibles = [c for c, _ in constants.TYPE_AGENT_CHOICES]
    agents_equipe_ids = list(
        Agent.objects.filter(
            superviseur_id=superviseur_id, type_agent__in=types_cibles
        ).values_list("id", flat=True)
    )

    if granularite == "semaine":
        ModeleEquipe = VwPerformanceSuperviseurSemaine
        ModeleAgents = VwPerformanceAgentSemaine
        champ_periode = "semaine"
        semaines_disponibles = list(
            VwPerformanceSuperviseurSemaine.objects.filter(superviseur_id=superviseur_id)
            .order_by("-semaine")
            .values_list("semaine", flat=True)
            .distinct()[:26]
        )
        semaine_demandee = parse_date(request.GET.get("semaine") or "")
        periode_courante_val = (
            semaine_demandee
            if semaine_demandee in semaines_disponibles
            else (semaines_disponibles[0] if semaines_disponibles else None)
        )
        context["semaines_disponibles"] = semaines_disponibles
        context["semaine_selectionnee"] = periode_courante_val
        if periode_courante_val:
            date_debut_periode = periode_courante_val
            date_fin_periode = periode_courante_val + timedelta(days=6)
            context["periode_libelle"] = (
                f"Semaine du {date_debut_periode:%d/%m/%Y} au {date_fin_periode:%d/%m/%Y}"
            )
            periode_precedente_val = periode_courante_val - timedelta(weeks=1)
            periode_precedente_libelle = f"la semaine du {periode_precedente_val:%d/%m/%Y}"
        else:
            date_debut_periode = date_fin_periode = None
            periode_precedente_val = None
            periode_precedente_libelle = None
    else:
        ModeleEquipe = VwPerformanceSuperviseur
        ModeleAgents = VwPerformanceAgent
        champ_periode = "mois"
        context["periode_libelle"] = f"{MOIS_FR[mois]} {annee}"
        periode_courante_val = date(annee, mois, 1)
        date_debut_periode = periode_courante_val
        date_fin_periode = date(annee, mois, calendar.monthrange(annee, mois)[1])
        annee_prec, mois_prec = _mois_precedent(annee, mois)
        periode_precedente_val = date(annee_prec, mois_prec, 1)
        periode_precedente_libelle = f"{MOIS_FR[mois_prec]} {annee_prec}"

    equipe_courante = (
        ModeleEquipe.objects.filter(
            superviseur_id=superviseur_id, **{champ_periode: periode_courante_val}
        ).first()
        if periode_courante_val
        else None
    )
    equipe_precedente = (
        ModeleEquipe.objects.filter(
            superviseur_id=superviseur_id, **{champ_periode: periode_precedente_val}
        ).first()
        if periode_precedente_val
        else None
    )

    delta_kg_vendus = None
    delta_kg_vendus_pct = None
    if equipe_courante and equipe_precedente:
        delta_kg_vendus = equipe_courante.kg_vendus - equipe_precedente.kg_vendus
        if equipe_precedente.kg_vendus:
            delta_kg_vendus_pct = float(delta_kg_vendus / equipe_precedente.kg_vendus * 100)

    # ---- Objectif équipe (somme des 50 kg/jour des agents actifs) ----
    nb_agents_actifs = equipe_courante.nb_agents_actifs if equipe_courante else 0
    jours_ouvres_periode = (
        _jours_ouvres_dans_periode(date_debut_periode, date_fin_periode)
        if date_debut_periode
        else 0
    )
    objectif_kg_jour_equipe = nb_agents_actifs * 50
    kg_par_jour_equipe = (
        (equipe_courante.kg_vendus / jours_ouvres_periode)
        if (equipe_courante and jours_ouvres_periode)
        else Decimal("0.00")
    )
    kg_par_jour_moyen_agent = (
        (kg_par_jour_equipe / nb_agents_actifs) if nb_agents_actifs else Decimal("0.00")
    )
    if not nb_agents_actifs:
        statut_equipe = "sous_objectif"
    elif kg_par_jour_moyen_agent >= 50:
        statut_equipe = "atteint"
    elif kg_par_jour_moyen_agent >= 40:
        statut_equipe = "proche"
    else:
        statut_equipe = "sous_objectif"

    # ---- CA moyen par agent vs cible ----
    ca_moyen_par_agent = (
        (equipe_courante.ca / nb_agents_actifs) if (equipe_courante and nb_agents_actifs) else None
    )

    # ---- Tendance équipe sur 6 périodes ----
    if granularite == "semaine":
        debut_tendance = (
            periode_courante_val - timedelta(weeks=NB_PERIODES_TENDANCE - 1)
            if periode_courante_val
            else None
        )
        tendance_qs = (
            ModeleEquipe.objects.filter(
                superviseur_id=superviseur_id,
                semaine__gte=debut_tendance,
                semaine__lte=periode_courante_val,
            ).order_by("semaine")
            if debut_tendance
            else ModeleEquipe.objects.none()
        )
    else:
        annee_debut, mois_debut = _mois_moins_n(annee, mois, NB_PERIODES_TENDANCE - 1)
        tendance_qs = ModeleEquipe.objects.filter(
            superviseur_id=superviseur_id,
            mois__gte=date(annee_debut, mois_debut, 1),
            mois__lte=periode_courante_val,
        ).order_by("mois")
    tendance = list(tendance_qs)
    for t in tendance:
        t.periode = getattr(t, champ_periode)

    # ---- Agents de l'équipe (drill-down vers leur propre fiche) ----
    agents_equipe = (
        list(
            ModeleAgents.objects.filter(
                superviseur_id=superviseur_id, **{champ_periode: periode_courante_val}
            ).order_by("-kg_par_jour")
        )
        if periode_courante_val
        else []
    )
    agents_precedent_kg = (
        dict(
            ModeleAgents.objects.filter(
                superviseur_id=superviseur_id, **{champ_periode: periode_precedente_val}
            ).values_list("agent_id", "kg_vendus")
        )
        if periode_precedente_val
        else {}
    )
    for a in agents_equipe:
        a.statut_couleur = constants.statut_objectif_agent(a.statut_objectif_50kg)
        a.statut_label = constants.STATUT_OBJECTIF_LABELS.get(a.statut_objectif_50kg, "—")
        kg_prec = agents_precedent_kg.get(a.agent_id)
        a.kg_vendus_precedent = kg_prec
        a.kg_vendus_delta = (a.kg_vendus - kg_prec) if kg_prec is not None else None

    # ---- Produits vendus par l'équipe (toujours mois, comme la fiche agent) + comparaison n-1 ----
    mois_courant_date = date(annee, mois, 1)
    annee_prec_produits, mois_prec_produits = _mois_precedent(annee, mois)
    mois_precedent_date = date(annee_prec_produits, mois_prec_produits, 1)
    mois_precedent_libelle_produits = f"{MOIS_FR[mois_prec_produits]} {annee_prec_produits}"

    produits_base_qs = VwVentesAgentProduit.objects.filter(
        agent_id__in=agents_equipe_ids, mois=mois_courant_date
    )
    produits_options = list(
        produits_base_qs.values("produit_id", "produit_nom").distinct().order_by("produit_nom")
    )
    produit_filtre = request.GET.get("produit")
    produits_qs = produits_base_qs
    if produit_filtre:
        produits_qs = produits_qs.filter(produit_id=produit_filtre)
    produits = list(
        produits_qs.values("produit_id", "produit_nom")
        .annotate(
            kg_vendus=Sum("kg_vendus"), ca_total=Sum("ca_total"),
            marge=Sum("marge"), nombre_ventes=Sum("nombre_ventes"),
        )
        .order_by("-kg_vendus")
    )
    produits_precedent_kg = dict(
        VwVentesAgentProduit.objects.filter(
            agent_id__in=agents_equipe_ids, mois=mois_precedent_date
        )
        .values("produit_id")
        .annotate(kg_vendus=Sum("kg_vendus"))
        .values_list("produit_id", "kg_vendus")
    )
    for p in produits:
        kg_prec = produits_precedent_kg.get(p["produit_id"])
        p["kg_vendus_precedent"] = kg_prec
        p["kg_vendus_delta"] = (p["kg_vendus"] - kg_prec) if kg_prec is not None else None

    # ---- Filtre produit : influence aussi le tableau agents (kg vendus + delta de CE produit
    # uniquement), disponible seulement en vue mois — VwVentesAgentProduit n'a pas de grain
    # hebdomadaire (cf. sprint-10/11, "toujours au grain mensuel"). ----
    if produit_filtre and granularite == "mois":
        agent_produit_courant = dict(
            VwVentesAgentProduit.objects.filter(
                agent_id__in=agents_equipe_ids, produit_id=produit_filtre, mois=mois_courant_date
            ).values_list("agent_id", "kg_vendus")
        )
        agent_produit_precedent = dict(
            VwVentesAgentProduit.objects.filter(
                agent_id__in=agents_equipe_ids, produit_id=produit_filtre, mois=mois_precedent_date
            ).values_list("agent_id", "kg_vendus")
        )
        for a in agents_equipe:
            a.kg_vendus_produit = agent_produit_courant.get(a.agent_id, Decimal("0.00"))
            kg_prec_produit = agent_produit_precedent.get(a.agent_id)
            a.kg_vendus_produit_precedent = kg_prec_produit
            a.kg_vendus_produit_delta = (
                (a.kg_vendus_produit - kg_prec_produit) if kg_prec_produit is not None else None
            )

    # ---- Stock en main agrégé de l'équipe (snapshot batch) ----
    stock = list(
        FctStockAgent.objects.filter(agent_id__in=agents_equipe_ids)
        .values("produit_id", "produit_nom")
        .annotate(stock_restant_kg=Sum("stock_restant_kg"))
        .order_by("-stock_restant_kg")
    )
    stock_total_kg = sum((s["stock_restant_kg"] for s in stock), Decimal("0.00"))

    if not equipe_courante and not agents_equipe and not produits and not stock:
        context["est_vide"] = True
        context["superviseur"] = superviseur
        return render(request, "bi/dashboard_superviseur_detail.html", context)

    tendance_labels = (
        [f"S{t.periode:%W} ({t.periode:%d/%m})" for t in tendance]
        if granularite == "semaine"
        else [f"{MOIS_FR[t.periode.month][:3]} {t.periode.year}" for t in tendance]
    )

    # ---- Courbes produit sur le même graphique que le volume (bar = volume équipe, ligne par
    # produit) — mois uniquement (pas de grain hebdomadaire pour vw_ventes_agent_produit). Sans
    # filtre : les 5 produits les plus vendus sur la fenêtre, pour ne pas surcharger le
    # graphique. Avec filtre : uniquement le produit sélectionné. ----
    PALETTE_PRODUITS = ["#c9a83a", "#7a4fb5", "#2f9e6f", "#c0563a", "#3a7fc0"]
    courbes_produits = []
    if granularite == "mois" and tendance:
        annee_debut, mois_debut = _mois_moins_n(annee, mois, NB_PERIODES_TENDANCE - 1)
        ventes_fenetre = VwVentesAgentProduit.objects.filter(
            agent_id__in=agents_equipe_ids,
            mois__gte=date(annee_debut, mois_debut, 1),
            mois__lte=mois_courant_date,
        )
        if produit_filtre:
            ventes_fenetre = ventes_fenetre.filter(produit_id=produit_filtre)
            produits_a_tracer = list(
                ventes_fenetre.values_list("produit_id", "produit_nom").distinct()
            )
        else:
            produits_a_tracer = list(
                ventes_fenetre.values("produit_id", "produit_nom")
                .annotate(total=Sum("kg_vendus"))
                .order_by("-total")
                .values_list("produit_id", "produit_nom")[:5]
            )
        par_produit_mois = {
            (row["produit_id"], row["mois"]): row["kg_vendus"]
            for row in ventes_fenetre.values("produit_id", "mois").annotate(kg_vendus=Sum("kg_vendus"))
        }
        for i, (pid, pnom) in enumerate(produits_a_tracer):
            courbes_produits.append(
                {
                    "label": pnom,
                    "color": PALETTE_PRODUITS[i % len(PALETTE_PRODUITS)],
                    "data": [
                        float(par_produit_mois.get((pid, t.periode), 0) or 0) for t in tendance
                    ],
                }
            )

    tendance_chart = _chart_json(
        {
            "labels": tendance_labels,
            "kg_vendus": [float(t.kg_vendus or 0) for t in tendance],
            "produits": courbes_produits,
        }
    )

    context.update(
        {
            "superviseur": superviseur,
            "equipe_courante": equipe_courante,
            "nb_agents_actifs": nb_agents_actifs,
            "jours_ouvres_periode": jours_ouvres_periode,
            "objectif_kg_jour_equipe": objectif_kg_jour_equipe,
            "kg_par_jour_equipe": kg_par_jour_equipe,
            "statut_equipe": statut_equipe,
            "statut_couleur_equipe": constants.statut_objectif_agent(statut_equipe),
            "statut_label_equipe": constants.STATUT_OBJECTIF_LABELS.get(statut_equipe, "—"),
            "ca_moyen_par_agent": ca_moyen_par_agent,
            "statut_ca_moyen": constants.statut_ca_moyen_agent(ca_moyen_par_agent),
            "ca_moyen_cible": constants.CA_MOYEN_AGENT_CIBLE,
            "delta_kg_vendus": delta_kg_vendus,
            "delta_kg_vendus_pct": delta_kg_vendus_pct,
            "periode_precedente_libelle": periode_precedente_libelle,
            "tendance": tendance,
            "tendance_chart": tendance_chart,
            "agents_equipe": agents_equipe,
            "produits": produits,
            "produits_options": produits_options,
            "produit_filtre": int(produit_filtre) if produit_filtre else None,
            "mois_produits_libelle": f"{MOIS_FR[mois]} {annee}",
            "mois_precedent_libelle_produits": mois_precedent_libelle_produits,
            "stock": stock,
            "stock_total_kg": stock_total_kg,
        }
    )
    return render(request, "bi/dashboard_superviseur_detail.html", context)


@bi_access_required
def dashboard_depenses(request):
    titre = dict(constants.DASHBOARDS)["depenses"]
    context = _base_context(request, "depenses", titre)
    annee, mois = context["annee"], context["mois"]

    depenses_qs = VwDepensesCategorie.objects.order_by("-montant")
    if annee:
        depenses_qs = depenses_qs.filter(mois__year=annee)
    if mois:
        depenses_qs = depenses_qs.filter(mois__month=mois)
    depenses = list(depenses_qs)

    if not depenses:
        context["est_vide"] = True
        return render(request, "bi/dashboard_depenses.html", context)

    depenses_chart = _chart_json(
        {
            "labels": [d.categorie or "Non catégorisé" for d in depenses],
            "montant": [d.montant for d in depenses],
        }
    )

    context.update({"depenses": depenses, "depenses_chart": depenses_chart})
    return render(request, "bi/dashboard_depenses.html", context)


@bi_access_required
def dashboard_stock(request):
    titre = dict(constants.DASHBOARDS)["stock"]
    context = _base_context(request, "stock", titre)
    annee, mois = context["annee"], context["mois"]

    stock_base = VwAnalyseStock.objects.filter(valeur_stock__gt=0)
    produit_options = list(
        stock_base.exclude(produit_id__isnull=True)
        .values_list("produit_id", "produit_nom")
        .distinct()
        .order_by("produit_nom")
    )

    fournisseurs_par_id = dict(
        stock_base.exclude(fournisseur_id__isnull=True)
        .values_list("fournisseur_id", "fournisseur_nom")
        .distinct()
    )
    fournisseurs_par_id.update(
        VwMargeFournisseur.objects.exclude(fournisseur_id__isnull=True)
        .values_list("fournisseur_id", "fournisseur_nom")
        .distinct()
    )
    fournisseur_options = sorted(fournisseurs_par_id.items(), key=lambda item: item[1] or "")

    produit_filtre = request.GET.get("produit")
    fournisseur_filtre = request.GET.get("fournisseur")

    stock_qs = stock_base
    if produit_filtre:
        stock_qs = stock_qs.filter(produit_id=produit_filtre)
    if fournisseur_filtre:
        stock_qs = stock_qs.filter(fournisseur_id=fournisseur_filtre)
    stock = list(stock_qs.order_by("-valeur_stock"))
    total_stock = stock_qs.aggregate(total=Sum("valeur_stock"))["total"]

    marge_qs = VwMargeFournisseur.objects.all()
    if annee:
        marge_qs = marge_qs.filter(mois__year=annee)
    if mois:
        marge_qs = marge_qs.filter(mois__month=mois)
    if fournisseur_filtre:
        marge_qs = marge_qs.filter(fournisseur_id=fournisseur_filtre)
    if produit_filtre:
        marge_qs = marge_qs.filter(produit_id=produit_filtre)

    # Une marge par fournisseur x produit x mois est illisible en un coup d'œil (24/07/2026,
    # décision produit) : deux vues agrégées à la place — marge par fournisseur (tous produits
    # confondus) et marge par produit (tous fournisseurs confondus), toutes deux réactives aux
    # filtres produit/fournisseur/période déjà en place sur la page.
    marge_par_fournisseur = list(
        marge_qs.values("fournisseur_id", "fournisseur_nom")
        .annotate(ca=Sum("ca"), marge=Sum("marge_calibree"))
        .order_by("-marge")
    )
    marge_par_produit = list(
        marge_qs.values("produit_id", "produit_nom")
        .annotate(ca=Sum("ca"), marge=Sum("marge_calibree"))
        .order_by("-marge")
    )

    ajustements_par_fournisseur = {
        c["lot__fournisseur_id"]: c["n"]
        for c in AjustementPrixAchat.objects.values("lot__fournisseur_id").annotate(n=Count("id"))
    }
    ajustements_par_produit = {
        c["lot__produit_id"]: c["n"]
        for c in AjustementPrixAchat.objects.values("lot__produit_id").annotate(n=Count("id"))
    }

    if not stock and not marge_par_fournisseur:
        context["est_vide"] = True
        context.update(
            {
                "produit_options": produit_options,
                "fournisseur_options": fournisseur_options,
                "produit_filtre": int(produit_filtre) if produit_filtre else None,
                "fournisseur_filtre": int(fournisseur_filtre) if fournisseur_filtre else None,
            }
        )
        return render(request, "bi/dashboard_stock.html", context)

    for s in stock:
        s.statut = constants.statut_jours_stock(s.jours_en_stock_moyen)

    for f in marge_par_fournisseur:
        f["marge_pct"] = (f["marge"] / f["ca"] * 100) if f["ca"] else None
        f["statut"] = constants.statut_marge(f["marge"], f["marge_pct"])
        f["nb_ajustements"] = ajustements_par_fournisseur.get(f["fournisseur_id"], 0)

    for p in marge_par_produit:
        p["marge_pct"] = (p["marge"] / p["ca"] * 100) if p["ca"] else None
        p["statut"] = constants.statut_marge(p["marge"], p["marge_pct"])
        p["nb_ajustements"] = ajustements_par_produit.get(p["produit_id"], 0)

    context.update(
        {
            "stock": stock,
            "total_stock": total_stock,
            "total_stock_statut": constants.statut_valeur_stock(total_stock),
            "marge_par_fournisseur": marge_par_fournisseur,
            "marge_par_produit": marge_par_produit,
            "produit_options": produit_options,
            "fournisseur_options": fournisseur_options,
            "produit_filtre": int(produit_filtre) if produit_filtre else None,
            "fournisseur_filtre": int(fournisseur_filtre) if fournisseur_filtre else None,
        }
    )
    return render(request, "bi/dashboard_stock.html", context)
