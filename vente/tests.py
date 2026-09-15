from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import (
    Agent,
    CorrectionAdministrative,
    DetailDistribution,
    DistributionAgent,
    LotEntrepot,
    Produit,
    Recouvrement,
    Vente,
)
from vente.services import CorrectionVenteService


class CorrectionVenteServiceTests(TestCase):
    """sprint-13 — correction administrative du prix et/ou de la quantité
    d'une Vente déjà enregistrée."""

    def setUp(self):
        produit = Produit.objects.create(nom='huile')
        self.utilisateur = User.objects.create_user(username='mdmaiga', password='x')

        sup_user = User.objects.create_user(username='sup1', password='x')
        self.superviseur = Agent.objects.create(user=sup_user, type_agent='entrepot')

        agent_user = User.objects.create_user(username='agent1', password='x')
        self.agent = Agent.objects.create(
            user=agent_user, type_agent='terrain', superviseur=self.superviseur
        )

        lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=Decimal('100.00'),
            quantite_restante=Decimal('100.00'),
            prix_achat_unitaire=Decimal('500.00'),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur, agent_terrain=self.agent, quantite_totale=Decimal('20.00')
        )
        self.detail = DetailDistribution.objects.create(
            distribution=distribution, lot=lot, quantite=Decimal('20.00')
        )

        self.vente = Vente.objects.create(
            agent=self.agent,
            detail_distribution=self.detail,
            quantite=Decimal('1.00'),
            prix_vente_unitaire=Decimal('800.00'),
            type_vente='detail',
        )
        self.recouvrement = Recouvrement.objects.create(
            agent=self.agent,
            superviseur=self.superviseur,
            vente=self.vente,
            montant_recouvre=self.vente.total_vente,
        )

    def test_corrige_prix_et_resynchronise_le_recouvrement(self):
        # Cas réel remonté : confusion prix au sac (25 kg) / prix au kilo.
        CorrectionVenteService.corriger_vente(
            self.vente.id,
            prix_vente_unitaire=Decimal('20000.00'),
            motif='Confusion prix sac / prix au kilo',
            utilisateur=self.utilisateur,
        )
        self.vente.refresh_from_db()
        self.recouvrement.refresh_from_db()

        self.assertEqual(self.vente.prix_vente_unitaire, Decimal('20000.00'))
        self.assertEqual(self.recouvrement.montant_recouvre, Decimal('20000.00'))

        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'VENTE_PRIX_QUANTITE')

    def test_corrige_quantite_ajuste_quantite_vendue_du_detail(self):
        ancienne = self.detail.quantite_vendue
        CorrectionVenteService.corriger_vente(
            self.vente.id,
            quantite=Decimal('3.00'),
            motif='Erreur de quantité saisie',
            utilisateur=self.utilisateur,
        )
        self.detail.refresh_from_db()
        self.assertEqual(self.detail.quantite_vendue, ancienne + Decimal('2.00'))

    def test_refuse_quantite_superieure_au_disponible(self):
        with self.assertRaises(ValidationError):
            CorrectionVenteService.corriger_vente(
                self.vente.id,
                quantite=Decimal('50.00'),
                motif='test',
                utilisateur=self.utilisateur,
            )
        self.assertEqual(CorrectionAdministrative.objects.count(), 0)

    def test_motif_facultatif(self):
        CorrectionVenteService.corriger_vente(
            self.vente.id,
            prix_vente_unitaire=Decimal('900.00'),
            motif='',
            utilisateur=self.utilisateur,
        )
        self.assertEqual(CorrectionAdministrative.objects.get().motif, '')

    def test_corrige_date_conserve_heure_et_journalise(self):
        ancienne_date = self.vente.date_vente
        nouvelle_date = date(2026, 5, 1)

        CorrectionVenteService.corriger_vente(
            self.vente.id,
            date_vente=nouvelle_date,
            motif='Date de vente erronée',
            utilisateur=self.utilisateur,
        )
        self.vente.refresh_from_db()

        self.assertEqual(self.vente.date_vente.date(), nouvelle_date)
        self.assertEqual(self.vente.date_vente.time(), ancienne_date.time())

        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'VENTE_DATE')
