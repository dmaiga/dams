"""Tests des vues bi.

Les 6 modèles managed=False (VwRentabiliteGlobale, VwRentabiliteProduit,
VwPerformanceSuperviseur, VwPerformanceAgent, VwAnalyseStock, VwMargeFournisseur) lisent des
vues PostgreSQL créées par dbt (bi_.vw_*) — Django ne les crée jamais dans la base de test
(managed=False n'est pas migré). Approche retenue : mocker le manager `objects` de chaque
modèle managed=False (unittest.mock, `patch.object(Modele, "objects", ...)`) plutôt que de
provisionner les vues bi_ dans la base de test (ce qui dupliquerait le SQL dbt et se
désynchroniserait de la source de vérité dbt_bi/models/marts/aggregates/*.sql). Seul
AjustementPrixAchat (managed=True) utilise la vraie base de test via @pytest.mark.django_db.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from bi.models import (
    VwAnalyseStock,
    VwMargeFournisseur,
    VwPerformanceAgent,
    VwPerformanceSuperviseur,
    VwRentabiliteGlobale,
    VwRentabiliteProduit,
)


@pytest.fixture
def utilisateur_connecte(client, django_user_model):
    user = django_user_model.objects.create_user(username="direction.test", password="test-pass-123")
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_sommaire_redirige_si_non_connecte(client):
    response = client.get(reverse("bi:sommaire"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_sommaire_ok(client, utilisateur_connecte):
    response = client.get(reverse("bi:sommaire"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_sante_avec_donnees(client, utilisateur_connecte):
    ligne = SimpleNamespace(
        mois=__import__("datetime").date(2026, 6, 1),
        ca=Decimal("15000000"),
        cout_achat=Decimal("7500000"),
        marge_brute=Decimal("7500000"),
        marge_pct=Decimal("50.00"),
        cout_salaires=Decimal("1200000"),
        cout_depenses=Decimal("400000"),
        rentabilite_nette=Decimal("2500000"),
    )
    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale, patch.object(
        VwPerformanceSuperviseur, "objects"
    ) as mock_superviseur:
        mock_globale.order_by.return_value = [ligne]
        mock_superviseur.order_by.return_value.values.return_value = [
            {"superviseur_nom": "Fatou", "ca": Decimal("5000000")}
        ]
        response = client.get(reverse("bi:sante"))

    assert response.status_code == 200
    kpis = {k["code"]: k for k in response.context["kpis"]}
    assert kpis["KPI-009"]["valeur"] == Decimal("2500000")
    assert kpis["KPI-009"]["statut"] == "vert"


@pytest.mark.django_db
def test_dashboard_sante_etat_vide(client, utilisateur_connecte):
    with patch.object(VwRentabiliteGlobale, "objects") as mock_globale:
        mock_globale.order_by.return_value = []
        response = client.get(reverse("bi:sante"))

    assert response.status_code == 200
    assert response.context["est_vide"] is True


@pytest.mark.django_db
def test_dashboard_produits_ok(client, utilisateur_connecte):
    produit = SimpleNamespace(
        produit_id=1,
        produit_nom="Riz",
        ca=Decimal("1000000"),
        cout_achat=Decimal("400000"),
        marge=Decimal("600000"),
        marge_pct=Decimal("60.00"),
        quantite_vendue_kg=Decimal("500"),
        stock_moyen=Decimal("100000"),
        rotation_stock=Decimal("10"),
    )
    with patch.object(VwRentabiliteProduit, "objects") as mock_produit:
        mock_produit.order_by.return_value = [produit]
        mock_produit.filter.return_value.count.return_value = 0
        response = client.get(reverse("bi:produits"))

    assert response.status_code == 200
    assert response.context["nb_deficitaires"] == 0
    assert response.context["produits"][0].statut == "vert"


@pytest.mark.django_db
def test_dashboard_superviseurs_ok(client, utilisateur_connecte):
    superviseur = SimpleNamespace(
        superviseur_id=1,
        superviseur_nom="Ismael",
        ca=Decimal("3000000"),
        marge_brute=Decimal("1500000"),
        cout_equipe=Decimal("500000"),
        rentabilite_nette=Decimal("1000000"),
        nb_agents_actifs=5,
        ca_moyen_par_agent=Decimal("600000"),
    )
    with patch.object(VwPerformanceSuperviseur, "objects") as mock_sup:
        mock_sup.order_by.return_value = [superviseur]
        response = client.get(reverse("bi:superviseurs"))

    assert response.status_code == 200
    assert response.context["superviseurs"][0].statut == "vert"


@pytest.mark.django_db
def test_dashboard_agents_ok(client, utilisateur_connecte):
    agent = SimpleNamespace(
        agent_id=1,
        nom_complet="Aminata Traoré",
        type_agent="terrain",
        kg_vendus=Decimal("250"),
        jours_actifs=5,
        kg_par_jour=Decimal("50.00"),
        statut_objectif_50kg="atteint",
        marge=Decimal("100000"),
        incentive=Decimal("6250"),
        rentabilite_agent=Decimal("93750"),
        ratio_incentive_marge_pct=Decimal("6.25"),
    )
    with patch.object(VwPerformanceAgent, "objects") as mock_agent:
        mock_agent.order_by.return_value = [agent]
        response = client.get(reverse("bi:agents"))

    assert response.status_code == 200
    assert response.context["agents"][0].statut_couleur == "vert"
    assert response.context["agents"][0].statut_label == "✅ Atteint"


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
    fournisseur_ligne = SimpleNamespace(
        fournisseur_mois_id=1,
        fournisseur_id=1,
        fournisseur_nom="Fournisseur A",
        mois=datetime.date(2026, 6, 1),
        ca=Decimal("2000000"),
        cout_achat_systeme=Decimal("1000000"),
        marge_systeme=Decimal("1000000"),
        marge_pct_systeme=Decimal("50.00"),
        prix_achat_corrige_pondere=None,
        calibre=False,
        cout_achat_calibre=Decimal("1000000"),
        marge_calibree=Decimal("1000000"),
        marge_calibree_pct=Decimal("50.00"),
    )
    with patch.object(VwAnalyseStock, "objects") as mock_stock, patch.object(
        VwMargeFournisseur, "objects"
    ) as mock_fourn:
        mock_stock.order_by.return_value = [stock_ligne]
        mock_stock.aggregate.return_value = {"total": Decimal("1000000")}
        mock_fourn.order_by.return_value = [fournisseur_ligne]
        response = client.get(reverse("bi:stock"))

    assert response.status_code == 200
    assert response.context["total_stock"] == Decimal("1000000")
    assert response.context["fournisseurs"][0].nb_ajustements == 0
