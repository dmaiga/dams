import json

from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Max, Sum
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from bi import constants
from bi.models import (
    AjustementPrixAchat,
    VwAnalyseStock,
    VwDepensesCategorie,
    VwMargeFournisseur,
    VwPerformanceAgent,
    VwPerformanceSuperviseur,
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

    # Graphique en journalier quand un mois précis est filtré (le cas par défaut désormais,
    # cf. _dernier_mois_disponible) : le grain mensuel de vw_rentabilite_globale réduirait sinon
    # la série à un seul point. En "Toutes périodes", on garde la tendance mensuelle multi-mois.
    chart_est_journalier = bool(annee and mois)
    if chart_est_journalier:
        jours = list(
            VwRentabiliteJournaliere.objects.filter(
                jour__year=annee, jour__month=mois
            ).order_by("jour")
        )
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


@bi_access_required
def dashboard_agents(request):
    """Performance Agent & Équipes : bloc superviseurs/équipes (KPI-201 à 206) suivi du détail
    agents vs objectif 50 kg/jour (KPI-301 à 306) — les deux filtrés par mois."""
    titre = dict(constants.DASHBOARDS)["agents"]
    context = _base_context(request, "agents", titre)
    annee, mois = context["annee"], context["mois"]

    superviseurs_qs = VwPerformanceSuperviseur.objects.order_by("-rentabilite_nette")
    if annee:
        superviseurs_qs = superviseurs_qs.filter(mois__year=annee)
    if mois:
        superviseurs_qs = superviseurs_qs.filter(mois__month=mois)
    superviseurs = list(superviseurs_qs)

    agents_qs = VwPerformanceAgent.objects.order_by("-kg_par_jour")
    if annee:
        agents_qs = agents_qs.filter(mois__year=annee)
    if mois:
        agents_qs = agents_qs.filter(mois__month=mois)
    superviseur_filtre = request.GET.get("superviseur")
    if superviseur_filtre:
        agents_qs = agents_qs.filter(superviseur_id=superviseur_filtre)
    agents = list(agents_qs)

    if not superviseurs and not agents:
        context["est_vide"] = True
        return render(request, "bi/dashboard_agents.html", context)

    for s in superviseurs:
        s.statut = constants.statut_rentabilite_superviseur(s.rentabilite_nette)

    for a in agents:
        a.statut_couleur = constants.statut_objectif_agent(a.statut_objectif_50kg)
        a.statut_label = constants.STATUT_OBJECTIF_LABELS.get(a.statut_objectif_50kg, "—")
        a.statut_rentabilite = constants.statut_rentabilite_agent(a.rentabilite_agent)
        a.statut_ratio = constants.statut_ratio_incentive_marge(a.ratio_incentive_marge_pct)

    superviseurs_chart = _chart_json(
        {
            "labels": [s.superviseur_nom for s in superviseurs],
            "rentabilite_nette": [s.rentabilite_nette for s in superviseurs],
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
            "agents": agents,
            "chart_data": chart_data,
            "superviseur_filtre": int(superviseur_filtre) if superviseur_filtre else None,
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

    fournisseurs_qs = VwMargeFournisseur.objects.order_by("-marge_calibree")
    if annee:
        fournisseurs_qs = fournisseurs_qs.filter(mois__year=annee)
    if mois:
        fournisseurs_qs = fournisseurs_qs.filter(mois__month=mois)
    if fournisseur_filtre:
        fournisseurs_qs = fournisseurs_qs.filter(fournisseur_id=fournisseur_filtre)
    if produit_filtre:
        fournisseurs_qs = fournisseurs_qs.filter(produit_id=produit_filtre)
    fournisseurs = list(fournisseurs_qs)

    ajustements_counts = {
        (c["lot__fournisseur_id"], c["lot__produit_id"], c["lot__date_reception__year"], c["lot__date_reception__month"]): c["n"]
        for c in AjustementPrixAchat.objects.values(
            "lot__fournisseur_id",
            "lot__produit_id",
            "lot__date_reception__year",
            "lot__date_reception__month",
        ).annotate(n=Count("id"))
    }

    if not stock and not fournisseurs:
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

    for f in fournisseurs:
        f.statut = constants.statut_marge_fournisseur(f.marge_calibree, f.marge_calibree_pct)
        f.nb_ajustements = ajustements_counts.get(
            (f.fournisseur_id, f.produit_id, f.mois.year, f.mois.month), 0
        )

    context.update(
        {
            "stock": stock,
            "total_stock": total_stock,
            "total_stock_statut": constants.statut_valeur_stock(total_stock),
            "fournisseurs": fournisseurs,
            "produit_options": produit_options,
            "fournisseur_options": fournisseur_options,
            "produit_filtre": int(produit_filtre) if produit_filtre else None,
            "fournisseur_filtre": int(fournisseur_filtre) if fournisseur_filtre else None,
        }
    )
    return render(request, "bi/dashboard_stock.html", context)
