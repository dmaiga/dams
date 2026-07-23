from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from bi.models import AjustementPrixAchat
from core.models import Fournisseur, LotEntrepot, Produit


@pytest.fixture
def lot(db):
    produit = Produit.objects.create(nom="Ail")
    fournisseur = Fournisseur.objects.create(nom="Fournisseur Test")
    return LotEntrepot.objects.create(
        produit=produit,
        fournisseur=fournisseur,
        quantite_initiale=Decimal("300"),
        quantite_restante=Decimal("300"),
        prix_achat_unitaire=Decimal("12000"),
        reference_lot="LOT-TEST-001",
    )


@pytest.fixture
def utilisateur(db):
    return User.objects.create_user(username="rot.test", password="test-pass-123")


@pytest.mark.django_db
def test_creation_ajustement_prix_achat(lot, utilisateur):
    ajustement = AjustementPrixAchat.objects.create(
        lot=lot,
        quantite_concernee=Decimal("150"),
        prix_achat_corrige=Decimal("11000"),
        justification="Renégociation post-réception, 150 unités à 11 000 FCFA au lieu de 12 000.",
        saisi_par=utilisateur,
    )
    assert ajustement.pk is not None
    assert ajustement.lot_id == lot.pk
    assert ajustement.lot.fournisseur == lot.fournisseur
    assert ajustement.lot.produit == lot.produit


@pytest.mark.django_db
def test_justification_obligatoire(lot, utilisateur):
    with pytest.raises(IntegrityError):
        AjustementPrixAchat.objects.create(
            lot=lot,
            quantite_concernee=Decimal("150"),
            prix_achat_corrige=Decimal("11000"),
            justification=None,
            saisi_par=utilisateur,
        )


@pytest.mark.django_db
def test_lot_renegocie_a_deux_prix_deux_lignes(lot, utilisateur):
    """Un même lot renégocié à deux prix (150 à 11000 puis 150 à 10000) se saisit en deux
    lignes distinctes pointant sur le même lot — cf. docstring bi/models.py."""
    premiere_moitie = AjustementPrixAchat.objects.create(
        lot=lot,
        quantite_concernee=Decimal("150"),
        prix_achat_corrige=Decimal("11000"),
        justification="Renégociation — première moitié à 11 000.",
        saisi_par=utilisateur,
    )
    seconde_moitie = AjustementPrixAchat.objects.create(
        lot=lot,
        quantite_concernee=Decimal("150"),
        prix_achat_corrige=Decimal("10000"),
        justification="Renégociation — seconde moitié à 10 000.",
        saisi_par=utilisateur,
    )
    assert AjustementPrixAchat.objects.filter(lot=lot).count() == 2
    total = (
        premiere_moitie.quantite_concernee * premiere_moitie.prix_achat_corrige
        + seconde_moitie.quantite_concernee * seconde_moitie.prix_achat_corrige
    )
    assert total == Decimal("3150000")


@pytest.mark.django_db
def test_contre_ajustement_annule_par_nouvelle_ligne(lot, utilisateur):
    """Append-only : un ajustement erroné s'annule par un contre-ajustement (nouvelle ligne,
    quantité négative), jamais par une modification de l'historique (cf. bi/models.py)."""
    premier = AjustementPrixAchat.objects.create(
        lot=lot,
        quantite_concernee=Decimal("300"),
        prix_achat_corrige=Decimal("12000"),
        justification="Saisie initiale (erronée).",
        saisi_par=utilisateur,
    )
    contre = AjustementPrixAchat.objects.create(
        lot=lot,
        quantite_concernee=Decimal("-300"),
        prix_achat_corrige=Decimal("12000"),
        justification="Annulation de la saisie initiale (erreur de quantité).",
        saisi_par=utilisateur,
    )
    assert AjustementPrixAchat.objects.filter(lot=lot).count() == 2
    total_quantite = premier.quantite_concernee + contre.quantite_concernee
    assert total_quantite == Decimal("0")
