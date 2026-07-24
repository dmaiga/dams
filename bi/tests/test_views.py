"""Tests des vues bi.

Les 7 modèles managed=False (VwRentabiliteGlobale, VwRentabiliteProduit,
VwPerformanceSuperviseur, VwPerformanceAgent, VwAnalyseStock, VwMargeFournisseur,
VwDepensesCategorie) lisent des vues PostgreSQL créées par dbt (bi_.vw_*) — Django ne les
crée jamais dans la base de test (managed=False n'est pas migré). Approche retenue : mocker
le manager `objects` de chaque modèle managed=False (unittest.mock,
`patch.object(Modele, "objects", ...)`) plutôt que de provisionner les vues bi_ dans la base
de test (ce qui dupliquerait le SQL dbt et se désynchroniserait de la source de vérité
dbt_bi/models/marts/aggregates/*.sql). Seul AjustementPrixAchat (managed=True) utilise la
vraie base de test via @pytest.mark.django_db.

Toutes les requêtes passent `?toutes_periodes=1` : depuis l'ajout du défaut "dernier mois
disponible" (bi/views.py:_dernier_mois_disponible), l'absence de ce paramètre déclencherait un
appel réel à VwRentabiliteGlobale.objects.aggregate(...), non mocké dans la plupart de ces
tests et donc en échec contre la base de test (vue bi_ absente). `test_dernier_mois_disponible`
couvre spécifiquement ce mécanisme.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from bi.views import _dernier_mois_disponible
from bi.models import (
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

TOUTES_PERIODES = {"toutes_periodes": "1"}


@pytest.fixture
def utilisateur_connecte(client, django_user_model):
    """Accès BI restreint à username='mdmaiga' (bi.views.bi_access_required, garde-fou
    temporaire par username, pas un rôle Django)."""
    user = django_user_model.objects.create_user(username="mdmaiga", password="test-pass-123")
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_sommaire_redirige_si_non_connecte(client):
    response = client.get(reverse("bi:sommaire"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_sommaire_redirige_si_utilisateur_non_autorise(client, django_user_model):
    user = django_user_model.objects.create_user(username="autre.utilisateur", password="test-pass-123")
    client.force_login(user)
    response = client.get(reverse("bi:sommaire"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_sommaire_ok(client, utilisateur_connecte):
    response = client.get(reverse("bi:sommaire"), TOUTES_PERIODES)
    assert response.status_code == 200


@pytest.mark.django_db
def test_dernier_mois_disponible_avec_donnees(client, utilisateur_connecte):
    import datetime

    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale:
        mock_globale.aggregate.return_value = {"mois__max": datetime.date(2026, 6, 1)}
        assert _dernier_mois_disponible() == (2026, 6)


@pytest.mark.django_db
def test_dernier_mois_disponible_sans_donnees_retombe_sur_aujourdhui(client, utilisateur_connecte):
    from django.utils import timezone

    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale:
        mock_globale.aggregate.return_value = {"mois__max": None}
        aujourdhui = timezone.now().date()
        assert _dernier_mois_disponible() == (aujourdhui.year, aujourdhui.month)


@pytest.mark.django_db
def test_dashboard_sante_avec_donnees(client, utilisateur_connecte):
    ligne = SimpleNamespace(
        mois=__import__("datetime").date(2026, 6, 1),
        ca=Decimal("15000000"),
        cout_achat=Decimal("7500000"),
        marge_brute=Decimal("7500000"),
        marge_pct=Decimal("50.00"),
        cout_salaires=Decimal("1200000"),
        salaires_pct=Decimal("8.00"),
        cout_depenses=Decimal("400000"),
        depenses_pct=Decimal("2.67"),
        rentabilite_nette=Decimal("2500000"),
        rentabilite_nette_pct=Decimal("16.67"),
    )
    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale:
        mock_globale.order_by.return_value = [ligne]
        mock_globale.filter.return_value.order_by.return_value.first.return_value = None
        response = client.get(reverse("bi:sante"), TOUTES_PERIODES)

    assert response.status_code == 200
    kpis_brute = {k["code"]: k for k in response.context["kpis_marge_brute"]}
    kpis_nette = {k["code"]: k for k in response.context["kpis_marge_nette"]}
    assert kpis_brute["KPI-003"]["valeur"] == Decimal("7500000")
    assert kpis_brute["KPI-003"]["principal"] is True
    assert kpis_nette["KPI-009"]["valeur"] == Decimal("2500000")
    assert kpis_nette["KPI-009"]["statut"] == "vert"
    assert response.context["chart_est_journalier"] is False


@pytest.mark.django_db
def test_dashboard_sante_graph_journalier_si_mois_precis(client, utilisateur_connecte):
    import datetime

    ligne = SimpleNamespace(
        mois=datetime.date(2026, 6, 1),
        ca=Decimal("15000000"),
        cout_achat=Decimal("7500000"),
        marge_brute=Decimal("7500000"),
        marge_pct=Decimal("50.00"),
        cout_salaires=Decimal("1200000"),
        salaires_pct=Decimal("8.00"),
        cout_depenses=Decimal("400000"),
        depenses_pct=Decimal("2.67"),
        rentabilite_nette=Decimal("2500000"),
        rentabilite_nette_pct=Decimal("16.67"),
    )
    jour = SimpleNamespace(
        jour=datetime.date(2026, 6, 15),
        ca=Decimal("500000"),
        cout_achat=Decimal("250000"),
        marge_brute=Decimal("250000"),
        cout_depenses=Decimal("10000"),
    )
    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale, patch.object(
        VwRentabiliteJournaliere, "objects"
    ) as mock_journaliere:
        mock_globale.order_by.return_value.filter.return_value.filter.return_value = [ligne]
        mock_globale.filter.return_value.order_by.return_value.first.return_value = None
        mock_journaliere.filter.return_value.order_by.return_value = [jour]
        response = client.get(reverse("bi:sante"), {"annee": "2026", "mois": "6"})

    assert response.status_code == 200
    assert response.context["chart_est_journalier"] is True
    mock_journaliere.filter.assert_called_once_with(jour__year=2026, jour__month=6)


@pytest.mark.django_db
def test_dashboard_sante_etat_vide(client, utilisateur_connecte):
    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale:
        mock_globale.order_by.return_value = []
        response = client.get(reverse("bi:sante"), TOUTES_PERIODES)

    assert response.status_code == 200
    assert response.context["est_vide"] is True


@pytest.mark.django_db
def test_dashboard_produits_ok(client, utilisateur_connecte):
    import datetime

    produit = SimpleNamespace(
        produit_id=1,
        produit_nom="Riz",
        mois=datetime.date(2026, 6, 1),
        ca=Decimal("1000000"),
        cout_achat=Decimal("400000"),
        marge=Decimal("600000"),
        marge_pct=Decimal("60.00"),
        quantite_vendue_kg=Decimal("500"),
        stock_moyen=Decimal("100000"),
        rotation_stock=Decimal("10"),
    )
    mock_qs = MagicMock()
    mock_qs.__iter__.return_value = iter([produit])
    mock_qs.filter.return_value.values.return_value.distinct.return_value.count.return_value = 0
    with patch.object(VwRentabiliteProduit, "objects") as mock_produit:
        mock_produit.order_by.return_value = mock_qs
        response = client.get(reverse("bi:produits"), TOUTES_PERIODES)

    assert response.status_code == 200
    assert response.context["nb_deficitaires"] == 0
    assert response.context["produits"][0].statut == "vert"


@pytest.mark.django_db
def test_dashboard_depenses_ok(client, utilisateur_connecte):
    depense = SimpleNamespace(
        depense_categorie_id=1,
        mois=__import__("datetime").date(2026, 6, 1),
        categorie="TRANSPORT_MARCHANDISE",
        montant=Decimal("850000"),
        montant_pct=Decimal("42.00"),
    )
    with patch.object(VwDepensesCategorie, "objects") as mock_dep:
        mock_dep.order_by.return_value = [depense]
        response = client.get(reverse("bi:depenses"), TOUTES_PERIODES)

    assert response.status_code == 200
    assert response.context["depenses"][0].categorie == "TRANSPORT_MARCHANDISE"


@pytest.mark.django_db
def test_dashboard_agents_ok(client, utilisateur_connecte):
    import datetime

    superviseur = SimpleNamespace(
        superviseur_id=1,
        superviseur_nom="Ismael",
        mois=datetime.date(2026, 6, 1),
        ca=Decimal("3000000"),
        marge_brute=Decimal("1500000"),
        kg_vendus=Decimal("1200"),
        cout_equipe=Decimal("500000"),
        rentabilite_nette=Decimal("1000000"),
        nb_agents_actifs=5,
        ca_moyen_par_agent=Decimal("600000"),
    )
    agent = SimpleNamespace(
        agent_id=1,
        nom_complet="Aminata Traoré",
        type_agent="terrain",
        superviseur_id=1,
        superviseur_nom="Ismael",
        mois=datetime.date(2026, 6, 1),
        kg_vendus=Decimal("250"),
        jours_actifs=5,
        jours_ouvres=26,
        kg_par_jour=Decimal("50.00"),
        statut_objectif_50kg="atteint",
        marge=Decimal("100000"),
        incentive=Decimal("6250"),
        rentabilite_agent=Decimal("93750"),
        ratio_incentive_marge_pct=Decimal("6.25"),
    )
    with patch.object(VwPerformanceSuperviseur, "objects") as mock_sup, patch.object(
        VwPerformanceAgent, "objects"
    ) as mock_agent:
        mock_sup.filter.return_value.order_by.return_value = [superviseur]
        mock_sup.filter.return_value.values_list.return_value = []
        mock_agent.filter.return_value.order_by.return_value = [agent]
        response = client.get(reverse("bi:agents"), {"annee": "2026", "mois": "6"})

    assert response.status_code == 200
    assert response.context["superviseurs"][0].kg_vendus == Decimal("1200")
    assert response.context["agents"][0].statut_couleur == "vert"
    assert response.context["agents"][0].statut_label == "✅ Atteint"


@pytest.mark.django_db
def test_dashboard_agents_filtre_superviseur(client, utilisateur_connecte):
    import datetime

    agent = SimpleNamespace(
        agent_id=1,
        nom_complet="Aminata Traoré",
        type_agent="terrain",
        superviseur_id=1,
        superviseur_nom="Ismael",
        mois=datetime.date(2026, 6, 1),
        kg_vendus=Decimal("250"),
        jours_actifs=5,
        jours_ouvres=26,
        kg_par_jour=Decimal("50.00"),
        statut_objectif_50kg="atteint",
        marge=Decimal("100000"),
        incentive=Decimal("6250"),
        rentabilite_agent=Decimal("93750"),
        ratio_incentive_marge_pct=Decimal("6.25"),
    )
    with patch.object(VwPerformanceSuperviseur, "objects") as mock_sup, patch.object(
        VwPerformanceAgent, "objects"
    ) as mock_agent:
        mock_sup.filter.return_value.order_by.return_value = []
        mock_sup.filter.return_value.values_list.return_value = []
        mock_agent.filter.return_value.order_by.return_value.filter.return_value = [agent]
        response = client.get(
            reverse("bi:agents"), {"annee": "2026", "mois": "6", "superviseur": "1"}
        )

    assert response.status_code == 200
    mock_agent.filter.return_value.order_by.return_value.filter.assert_called_once_with(
        superviseur_id="1"
    )
    assert response.context["superviseur_filtre"] == 1


@pytest.mark.django_db
def test_dashboard_agents_filtre_type_agent(client, utilisateur_connecte):
    import datetime

    agent = SimpleNamespace(
        agent_id=1,
        nom_complet="Aminata Traoré",
        type_agent="agent_gros",
        superviseur_id=1,
        superviseur_nom="Ismael",
        mois=datetime.date(2026, 6, 1),
        kg_vendus=Decimal("250"),
        jours_actifs=5,
        jours_ouvres=26,
        kg_par_jour=Decimal("50.00"),
        statut_objectif_50kg="atteint",
        marge=Decimal("100000"),
        incentive=Decimal("6250"),
        rentabilite_agent=Decimal("93750"),
        ratio_incentive_marge_pct=Decimal("6.25"),
    )
    with patch.object(VwPerformanceSuperviseur, "objects") as mock_sup, patch.object(
        VwPerformanceAgent, "objects"
    ) as mock_agent:
        mock_sup.filter.return_value.order_by.return_value = []
        mock_sup.filter.return_value.values_list.return_value = []
        mock_agent.filter.return_value.order_by.return_value.filter.return_value = [agent]
        response = client.get(
            reverse("bi:agents"), {"annee": "2026", "mois": "6", "type_agent": "agent_gros"}
        )

    assert response.status_code == 200
    mock_agent.filter.return_value.order_by.return_value.filter.assert_called_once_with(
        type_agent="agent_gros"
    )
    assert response.context["type_agent_filtre"] == "agent_gros"


@pytest.mark.django_db
def test_dashboard_agents_granularite_semaine(client, utilisateur_connecte):
    import datetime

    semaine = datetime.date(2026, 7, 20)
    superviseur = SimpleNamespace(
        superviseur_id=1,
        superviseur_nom="Ismael",
        semaine=semaine,
        ca=Decimal("700000"),
        marge_brute=Decimal("350000"),
        kg_vendus=Decimal("300"),
        nb_agents_actifs=5,
    )
    agent = SimpleNamespace(
        agent_id=1,
        nom_complet="Aminata Traoré",
        type_agent="terrain",
        superviseur_id=1,
        superviseur_nom="Ismael",
        semaine=semaine,
        kg_vendus=Decimal("60"),
        jours_actifs=5,
        jours_ouvres=6,
        kg_par_jour=Decimal("10.00"),
        statut_objectif_50kg="sous_objectif",
        marge=Decimal("20000"),
    )
    with patch.object(VwPerformanceSuperviseurSemaine, "objects") as mock_sup, patch.object(
        VwPerformanceAgentSemaine, "objects"
    ) as mock_agent:
        mock_agent.order_by.return_value.values_list.return_value.distinct.return_value = [
            semaine
        ]
        mock_sup.filter.return_value.order_by.return_value = [superviseur]
        mock_sup.filter.return_value.values_list.return_value = []
        mock_agent.filter.return_value.order_by.return_value = [agent]
        response = client.get(
            reverse("bi:agents"),
            {**TOUTES_PERIODES, "granularite": "semaine", "semaine": "2026-07-20"},
        )

    assert response.status_code == 200
    assert response.context["granularite"] == "semaine"
    assert response.context["semaine_selectionnee"] == semaine
    assert response.context["superviseurs"][0].kg_vendus == Decimal("300")
    # Pas d'incentive au grain semaine : la "rentabilité" affichée retombe sur la marge brute.
    assert response.context["agents"][0].rentabilite_affichee == Decimal("20000")


@pytest.mark.django_db
def test_dashboard_stock_ok(client, utilisateur_connecte):
    import datetime

    stock_ligne = SimpleNamespace(
        produit_id=1,
        produit_nom="Riz",
        fournisseur_id=1,
        fournisseur_nom="Fournisseur A",
        quantite_restante=Decimal("100"),
        valeur_stock=Decimal("1000000"),
        jours_en_stock_moyen=Decimal("20.0"),
    )
    marge_fournisseur_ligne = {
        "fournisseur_id": 1,
        "fournisseur_nom": "Fournisseur A",
        "ca": Decimal("2000000"),
        "marge": Decimal("1000000"),
    }
    marge_produit_ligne = {
        "produit_id": 1,
        "produit_nom": "Riz",
        "ca": Decimal("2000000"),
        "marge": Decimal("1000000"),
    }
    with patch.object(VwAnalyseStock, "objects") as mock_stock, patch.object(
        VwMargeFournisseur, "objects"
    ) as mock_fourn:
        mock_stock.filter.return_value.order_by.return_value = [stock_ligne]
        mock_stock.filter.return_value.aggregate.return_value = {"total": Decimal("1000000")}
        mock_distinct = mock_stock.filter.return_value.exclude.return_value.values_list.return_value.distinct.return_value
        mock_distinct.__iter__.return_value = iter([(1, "Fournisseur A")])
        mock_distinct.order_by.return_value = [(1, "Riz")]
        mock_fourn.exclude.return_value.values_list.return_value.distinct.return_value = [
            (1, "Fournisseur A")
        ]

        def values_side_effect(*args, **kwargs):
            resultat = MagicMock()
            if args == ("fournisseur_id", "fournisseur_nom"):
                resultat.annotate.return_value.order_by.return_value = [marge_fournisseur_ligne]
            else:
                resultat.annotate.return_value.order_by.return_value = [marge_produit_ligne]
            return resultat

        mock_fourn.all.return_value.values.side_effect = values_side_effect
        response = client.get(reverse("bi:stock"), TOUTES_PERIODES)

    assert response.status_code == 200
    assert response.context["total_stock"] == Decimal("1000000")
    assert response.context["marge_par_fournisseur"][0]["nb_ajustements"] == 0
    assert response.context["marge_par_produit"][0]["marge_pct"] == 50
    mock_stock.filter.assert_called_with(valeur_stock__gt=0)
