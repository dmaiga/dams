from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Agent,
    CorrectionAdministrative,
    DetailDistribution,
    DistributionAgent,
    LotEntrepot,
    Produit,
    Vente,
)


class CorrectionsAdministrativesAccessTests(TestCase):
    """sprint-13 — les 4 vues de correction sont réservées à mdmaiga."""

    def setUp(self):
        produit = Produit.objects.create(nom='tomate')

        self.mdmaiga_user = User.objects.create_user(username='mdmaiga', password='x')

        autre_user = User.objects.create_user(username='autre.direction', password='x')
        Agent.objects.create(user=autre_user, type_agent='direction')

        sup_user = User.objects.create_user(username='sup1', password='x')
        superviseur = Agent.objects.create(user=sup_user, type_agent='entrepot')
        agent_user = User.objects.create_user(username='agent1', password='x')
        agent = Agent.objects.create(user=agent_user, type_agent='terrain', superviseur=superviseur)

        self.lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=Decimal('100.00'),
            quantite_restante=Decimal('100.00'),
            prix_achat_unitaire=Decimal('250.00'),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=superviseur, agent_terrain=agent, quantite_totale=Decimal('20.00')
        )
        self.detail = DetailDistribution.objects.create(
            distribution=distribution, lot=self.lot, quantite=Decimal('20.00')
        )
        self.vente = Vente.objects.create(
            agent=agent,
            detail_distribution=self.detail,
            quantite=Decimal('1.00'),
            prix_vente_unitaire=Decimal('800.00'),
            type_vente='detail',
        )

    def _urls(self):
        return [
            reverse('corrections_hub'),
            reverse('corriger_lot', args=[self.lot.id]),
            reverse('corriger_distribution', args=[self.detail.id]),
            reverse('corriger_vente', args=[self.vente.id]),
            reverse('historique_corrections'),
        ]

    def test_utilisateur_non_mdmaiga_est_redirige(self):
        # @user_passes_test redirige vers le login (même comportement que la
        # réaffectation existante) — pas un 403, même pour un utilisateur
        # authentifié mais non autorisé.
        self.client.login(username='autre.direction', password='x')
        for url in self._urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertNotEqual(response.url, url)

    def test_utilisateur_anonyme_est_redirige_vers_login(self):
        for url in self._urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)

    def test_mdmaiga_accede_aux_4_ecrans(self):
        self.client.login(username='mdmaiga', password='x')
        for url in self._urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_correction_lot_via_formulaire_cree_une_seule_ligne_d_audit(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('corriger_lot', args=[self.lot.id]),
            {
                'quantite_initiale': '120.00',
                'prix_achat_unitaire': '',
                'date_reception': '',
                'motif': 'Erreur de saisie du gestionnaire de stock',
            },
        )
        self.assertRedirects(response, reverse('historique_corrections'))
        self.assertEqual(CorrectionAdministrative.objects.count(), 1)
        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'LOT_QUANTITE')
        self.assertTrue(correction.motif)

    def test_correction_lot_sans_motif_est_rejetee_par_le_formulaire(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('corriger_lot', args=[self.lot.id]),
            {
                'quantite_initiale': '120.00',
                'prix_achat_unitaire': '',
                'date_reception': '',
                'motif': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CorrectionAdministrative.objects.count(), 0)
        self.assertFalse(response.context['form'].is_valid())

    def test_hub_recherche_le_lot_par_produit(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.get(reverse('corrections_hub'), {'q_lot': 'tomate'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.lot, response.context['lots'])

    def test_hub_sans_recherche_ne_renvoie_aucun_resultat(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.get(reverse('corrections_hub'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['lots']), [])
        self.assertEqual(list(response.context['distributions']), [])
        self.assertEqual(list(response.context['ventes']), [])
