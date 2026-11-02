"""Groupe « Vérificateur général » : menu direction restreint + accès lecture aux écrans listés."""
import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from core.services.acces import GROUPE_VERIFICATEUR_GENERAL


@pytest.fixture
def verificateur(db, client):
    user = User.objects.create_user(username="verif", password="x")
    user.groups.add(Group.objects.get_or_create(name=GROUPE_VERIFICATEUR_GENERAL)[0])
    client.force_login(user)
    return user


def test_groupe_cree_par_migration(db):
    assert Group.objects.filter(name=GROUPE_VERIFICATEUR_GENERAL).exists()


def test_menu_restreint(client, verificateur):
    html = client.get(reverse("agent_dashboard")).content.decode()
    for libelle in ("Tableau de Bord", "Suivi des Distributions", "Analyse Opérationnelle", "Surveillance", "BI"):
        assert f"<span>{libelle}</span>" in html
    for libelle in ("Rémunération", "FINANCE", "Versements", "DAMS AGRO", "Corriger un lot"):
        assert f"<span>{libelle}</span>" not in html


def test_remuneration_refusee(client, verificateur):
    assert client.get(reverse("salaire_lecture")).status_code == 403


@pytest.mark.parametrize("nom", ["toutes_les_ventes", "dashboard_surveillance", "liste_fournisseurs_direction"])
def test_ecrans_ouverts(client, verificateur, nom):
    assert client.get(reverse(nom), {"toutes_periodes": "1"}).status_code == 200


def test_bi_autorise(verificateur):
    # Les vues bi_ (dbt) n'existent pas en base de test : on vérifie la garde d'accès seule.
    from bi.views import _est_utilisateur_autorise

    assert _est_utilisateur_autorise(verificateur)


def test_dams_agro_refuse(client, verificateur):
    assert client.get(reverse("agro_dashboard")).status_code == 403


def test_menu_restreint_meme_si_agent_direction(client, verificateur):
    from core.models import Agent

    Agent.objects.create(user=verificateur, type_agent="direction")
    html = client.get(reverse("agent_dashboard")).content.decode()
    assert "<span>DAMS AGRO</span>" not in html
    assert "<span>Rémunération</span>" not in html
