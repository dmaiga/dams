import json

from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Sum
from django.shortcuts import render
from django.urls import reverse

from bi import constants
from bi.models import (
    AjustementPrixAchat,
    VwAnalyseStock,
    VwDepensesCategorie,
    VwMargeFournisseur,
    VwPerformanceAgent,
    VwPerformanceSuperviseur,
    VwRentabiliteGlobale,
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


def _parse_periode(request):
    """Lit ?annee=&mois= depuis GET. Certaines vues bi_ (produit, superviseur, agent, stock)
    n'ont pas de dimension temporelle (grain all-time, cf. dbt_bi/models/marts/aggregates/*.sql)
    — annee/mois y sont propagés dans le sélecteur/les liens pour la cohérence de navigation
    mais ne filtrent que vw_rentabilite_globale et vw_marge_fournisseur (seules vues avec
    colonne `mois`)."""
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


@bi_access_required
def sommaire(request):
    context = _base_context(request, None, "Sommaire")
    return render(request, "bi/sommaire.html", context)


@bi_access_required
def dashboard_sante(request):
    titre = dict(constants.DASHBOARDS)["sante"]
    context = _base_context(request, "sante", titre)
    annee, mois = context["annee"], context["mois"]

    qs = VwRentabiliteGlobale.objects.order_by("mois")
    if annee:
        qs = qs.filter(mois__year=annee)
    if mois:
        qs = qs.filter(mois__month=mois)
    lignes = list(qs)

    if not lignes:
        context["est_vide"] = True
        return render(request, "bi/dashboard_sante.html", context)

    courante = lignes[-1]
    kpis = [
        {
            "code": "KPI-009",
            "label": "Rentabilité nette",
            "valeur": courante.rentabilite_nette,
            "unite": "FCFA",
            "statut": constants.statut_rentabilite_nette(courante.rentabilite_nette),
            "principal": True,
        },
        {
            "code": "KPI-001",
            "label": "Chiffre d'affaires",
            "valeur": courante.ca,
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
        {
            "code": "KPI-005",
            "label": "Coût salaires",
            "valeur": courante.cout_salaires,
            "unite": "FCFA",
            "statut": constants.NEUTRE,
        },
        {
            "code": "KPI-006",
            "label": "Coût salaires %",
            "valeur": courante.salaires_pct,
            "unite": "%",
            "statut": constants.statut_salaires_pct(courante.salaires_pct),
        },
        {
            "code": "KPI-007",
            "label": "Dépenses ROT",
            "valeur": courante.cout_depenses,
            "unite": "FCFA",
            "statut": constants.NEUTRE,
        },
        {
            "code": "KPI-008",
            "label": "Dépenses %",
            "valeur": courante.depenses_pct,
            "unite": "%",
            "statut": constants.statut_depenses_pct(courante.depenses_pct),
        },
    ]

    chart_data = _chart_json(
        {
            "labels": [f"{ligne.mois.month:02d}/{ligne.mois.year}" for ligne in lignes],
            "ca": [ligne.ca for ligne in lignes],
            "marge_brute": [ligne.marge_brute for ligne in lignes],
            "rentabilite_nette": [ligne.rentabilite_nette for ligne in lignes],
        }
    )

    repartition = list(
        VwPerformanceSuperviseur.objects.order_by("-ca").values("superviseur_nom", "ca")
    )
    repartition_chart = _chart_json(
        {
            "labels": [r["superviseur_nom"] for r in repartition],
            "ca": [r["ca"] for r in repartition],
        }
    )

    context.update(
        {
            "kpis": kpis,
            "chart_data": chart_data,
            "repartition_chart": repartition_chart,
        }
    )
    return render(request, "bi/dashboard_sante.html", context)


@bi_access_required
def dashboard_produits(request):
    titre = dict(constants.DASHBOARDS)["produits"]
    context = _base_context(request, "produits", titre)

    produits = list(VwRentabiliteProduit.objects.order_by("-marge"))
    if not produits:
        context["est_vide"] = True
        return render(request, "bi/dashboard_produits.html", context)

    for p in produits:
        p.statut = constants.statut_marge_produit(p.marge, p.marge_pct)

    nb_deficitaires = VwRentabiliteProduit.objects.filter(marge__lt=0).count()

    chart_data = _chart_json(
        {
            "labels": [p.produit_nom for p in produits],
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


@bi_access_required
def dashboard_superviseurs(request):
    titre = dict(constants.DASHBOARDS)["superviseurs"]
    context = _base_context(request, "superviseurs", titre)
    annee, mois = context["annee"], context["mois"]

    superviseurs = list(VwPerformanceSuperviseur.objects.order_by("-rentabilite_nette"))

    depenses_qs = VwDepensesCategorie.objects.order_by("-montant")
    if annee:
        depenses_qs = depenses_qs.filter(mois__year=annee)
    if mois:
        depenses_qs = depenses_qs.filter(mois__month=mois)
    depenses = list(depenses_qs)

    if not superviseurs and not depenses:
        context["est_vide"] = True
        return render(request, "bi/dashboard_superviseurs.html", context)

    for s in superviseurs:
        s.statut = constants.statut_rentabilite_superviseur(s.rentabilite_nette)

    chart_data = _chart_json(
        {
            "labels": [s.superviseur_nom for s in superviseurs],
            "rentabilite_nette": [s.rentabilite_nette for s in superviseurs],
        }
    )
    depenses_chart = _chart_json(
        {
            "labels": [d.categorie or "Non catégorisé" for d in depenses],
            "montant": [d.montant for d in depenses],
        }
    )

    context.update(
        {
            "superviseurs": superviseurs,
            "chart_data": chart_data,
            "depenses": depenses,
            "depenses_chart": depenses_chart,
        }
    )
    return render(request, "bi/dashboard_superviseurs.html", context)


@bi_access_required
def dashboard_agents(request):
    titre = dict(constants.DASHBOARDS)["agents"]
    context = _base_context(request, "agents", titre)

    agents = list(VwPerformanceAgent.objects.order_by("-kg_par_jour"))
    if not agents:
        context["est_vide"] = True
        return render(request, "bi/dashboard_agents.html", context)

    for a in agents:
        a.statut_couleur = constants.statut_objectif_agent(a.statut_objectif_50kg)
        a.statut_label = constants.STATUT_OBJECTIF_LABELS.get(a.statut_objectif_50kg, "—")
        a.statut_rentabilite = constants.statut_rentabilite_agent(a.rentabilite_agent)
        a.statut_ratio = constants.statut_ratio_incentive_marge(a.ratio_incentive_marge_pct)

    chart_data = _chart_json(
        {
            "labels": [a.nom_complet for a in agents],
            "kg_par_jour": [a.kg_par_jour for a in agents],
            "objectif": [50 for _ in agents],
        }
    )

    context.update({"agents": agents, "chart_data": chart_data})
    return render(request, "bi/dashboard_agents.html", context)


@bi_access_required
def dashboard_stock(request):
    titre = dict(constants.DASHBOARDS)["stock"]
    context = _base_context(request, "stock", titre)
    annee, mois = context["annee"], context["mois"]

    stock = list(VwAnalyseStock.objects.order_by("-valeur_stock"))
    total_stock = VwAnalyseStock.objects.aggregate(total=Sum("valeur_stock"))["total"]

    fournisseurs_qs = VwMargeFournisseur.objects.order_by("-marge_calibree")
    if annee:
        fournisseurs_qs = fournisseurs_qs.filter(mois__year=annee)
    if mois:
        fournisseurs_qs = fournisseurs_qs.filter(mois__month=mois)
    fournisseurs = list(fournisseurs_qs)

    ajustements_counts = {
        (c["fournisseur_id"], c["annee"], c["mois"]): c["n"]
        for c in AjustementPrixAchat.objects.values("fournisseur_id", "annee", "mois").annotate(
            n=Count("id")
        )
    }

    if not stock and not fournisseurs:
        context["est_vide"] = True
        return render(request, "bi/dashboard_stock.html", context)

    for s in stock:
        s.statut = constants.statut_jours_stock(s.jours_en_stock_moyen)

    for f in fournisseurs:
        f.statut = constants.statut_marge_fournisseur(f.marge_calibree, f.marge_calibree_pct)
        f.nb_ajustements = ajustements_counts.get((f.fournisseur_id, f.mois.year, f.mois.month), 0)

    context.update(
        {
            "stock": stock,
            "total_stock": total_stock,
            "total_stock_statut": constants.statut_valeur_stock(total_stock),
            "fournisseurs": fournisseurs,
        }
    )
    return render(request, "bi/dashboard_stock.html", context)
