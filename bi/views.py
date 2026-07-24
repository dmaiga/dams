import json
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Max, Sum
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from bi import constants
from bi.models import (
    AjustementPrixAchat,
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
)

# Accès BI restreint à un seul compte le temps de la mise au point (rendu à affiner, cf.
# session en cours) — pas un rôle Django, un simple garde-fou temporaire par username.
BI_USERNAME_AUTORISE = "mdmaiga"


def _est_utilisateur_autorise(user):
    return user.is_authenticated and user.username == BI_USERNAME_AUTORISE


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
def sommaire(request):
    context = _base_context(request, None, "Sommaire")
    return render(request, "bi/sommaire.html", context)


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
            "principal": True,
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

    context.update(
        {
            "kpis_marge_brute": kpis_marge_brute,
            "kpis_marge_nette": kpis_marge_nette,
            "chart_data": chart_data,
            "chart_est_journalier": chart_est_journalier,
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
            periode_precedente_libelle = f"la semaine du {semaine_precedente:%d/%m/%Y}"
        else:
            superviseurs_qs = VwPerformanceSuperviseurSemaine.objects.none()
            agents_qs = VwPerformanceAgentSemaine.objects.none()
            kg_vendus_precedents = {}
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
        periode_precedente_libelle = f"{MOIS_FR[mois_prec]} {annee_prec}"

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

    for a in agents:
        a.statut_couleur = constants.statut_objectif_agent(a.statut_objectif_50kg)
        a.statut_label = constants.STATUT_OBJECTIF_LABELS.get(a.statut_objectif_50kg, "—")
        # Grain semaine (VwPerformanceAgentSemaine) n'a pas d'incentive (fct_salaires est
        # mensuel, cf. commentaire dbt) : rentabilité affichée = marge brute dans ce cas.
        a.rentabilite_affichee = getattr(a, "rentabilite_agent", a.marge)
        a.statut_rentabilite = constants.statut_rentabilite_agent(a.rentabilite_affichee)

    superviseurs_chart = _chart_json(
        {
            "labels": [s.superviseur_nom for s in superviseurs],
            "kg_vendus": [s.kg_vendus for s in superviseurs],
        }
    )
    chart_data = _chart_json(
        {
            "labels": [a.nom_complet for a in agents],
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
        }
    )
    return render(request, "bi/dashboard_agents.html", context)


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
