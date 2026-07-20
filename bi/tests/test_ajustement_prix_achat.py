from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from bi.models import AjustementPrixAchat
from core.models import Fournisseur


@pytest.fixture
def fournisseur(db):
    return Fournisseur.objects.create(nom="Fournisseur Test")


@pytest.fixture
def utilisateur(db):
    return User.objects.create_user(username="rot.test", password="test-pass-123")


@pytest.mark.django_db
def test_creation_ajustement_prix_achat(fournisseur, utilisateur):
    ajustement = AjustementPrixAchat.objects.create(
        fournisseur=fournisseur,
        annee=2026,
        mois=6,
        quantite_concernee=Decimal("150"),
        prix_achat_corrige=Decimal("11000"),
        justification="Renégociation post-réception, 150 cartons à 11 000 FCFA au lieu de 12 000.",
        saisi_par=utilisateur,
    )
    assert ajustement.pk is not None
    assert ajustement.reference_lot == ""
    assert ajustement.produit is None


@pytest.mark.django_db
def test_justification_obligatoire(fournisseur, utilisateur):
    with pytest.raises(IntegrityError):
        AjustementPrixAchat.objects.create(
            fournisseur=fournisseur,
            annee=2026,
            mois=6,
            quantite_concernee=Decimal("150"),
            prix_achat_corrige=Decimal("11000"),
            justification=None,
            saisi_par=utilisateur,
        )


@pytest.mark.django_db
def test_contre_ajustement_annule_par_nouvelle_ligne(fournisseur, utilisateur):
    """Append-only : un ajustement erroné s'annule par un contre-ajustement (nouvelle ligne,
    quantité négative), jamais par une modification de l'historique (cf. bi/models.py)."""
    premier = AjustementPrixAchat.objects.create(
        fournisseur=fournisseur,
        annee=2026,
        mois=6,
        quantite_concernee=Decimal("300"),
        prix_achat_corrige=Decimal("12000"),
        justification="Saisie initiale (erronée).",
        saisi_par=utilisateur,
    )
    contre = AjustementPrixAchat.objects.create(
        fournisseur=fournisseur,
        annee=2026,
        mois=6,
        quantite_concernee=Decimal("-300"),
        prix_achat_corrige=Decimal("12000"),
        justification="Annulation de la saisie initiale (erreur de quantité).",
        saisi_par=utilisateur,
    )
    assert AjustementPrixAchat.objects.filter(fournisseur=fournisseur).count() == 2
    total_quantite = premier.quantite_concernee + contre.quantite_concernee
    assert total_quantite == Decimal("0")
