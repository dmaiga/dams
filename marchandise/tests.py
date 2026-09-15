import json
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import (
    Agent,
    AffectationLotSuperviseur,
    CorrectionAdministrative,
    DetailDistribution,
    DistributionAgent,
    Fournisseur,
    LotEntrepot,
    MouvementStock,
    Produit,
    Vente,
)
from marchandise.services import CorrectionDistributionService, CorrectionLotService

API_KEY = 'test-dams-champs-key'
URL = '/api/cessions/'


@override_settings(DAMS_CHAMPS_API_KEY=API_KEY)
class CessionReceptionAPITests(TestCase):

    def setUp(self):
        self.produit = Produit.objects.create(nom='concombre')

        user = User.objects.create_user(username='abdoulaye.kone', password='x')
        self.agent = Agent.objects.create(user=user, type_agent='entrepot')

    def _payload(self, **overrides):
        payload = {
            'idempotency_key': str(uuid.uuid4()),
            'produit': 'concombre',
            'quantite': '100.00',
            'prix_cession': '250.00',
            'date_cession': '2026-08-01',
        }
        payload.update(overrides)
        return payload

    def _post(self, payload, api_key=API_KEY):
        headers = {'HTTP_X_API_KEY': api_key} if api_key is not None else {}
        return self.client.post(
            URL,
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    # ------------------------------------------------------------------
    # 1. POST valide
    # ------------------------------------------------------------------
    def test_post_valide_cree_le_lot_entrepot(self):
        response = self._post(self._payload())

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'created')

        lot = LotEntrepot.objects.get(pk=data['lot_id'])
        self.assertEqual(lot.produit, self.produit)
        self.assertEqual(lot.fournisseur.nom, 'Champ DAMS')
        self.assertEqual(lot.quantite_initiale, Decimal('100.00'))
        self.assertEqual(lot.quantite_restante, Decimal('100.00'))
        self.assertEqual(lot.prix_achat_unitaire, Decimal('250.00'))
        self.assertEqual(lot.date_reception.date().isoformat(), '2026-08-01')
        self.assertEqual(lot.receptionne_par, self.agent)
        self.assertTrue(lot.reference_lot)
        self.assertEqual(str(lot.cession_idempotency_key), data['idempotency_key'])
        self.assertEqual(data['reference_lot'], lot.reference_lot)

    # ------------------------------------------------------------------
    # 2. Produit inexistant
    # ------------------------------------------------------------------
    def test_produit_inexistant_retourne_une_erreur(self):
        response = self._post(self._payload(produit='patate douce inconnue'))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LotEntrepot.objects.count(), 0)
        self.assertFalse(Produit.objects.filter(nom__icontains='patate').exists())

    # ------------------------------------------------------------------
    # 3. Agent de réception inexistant
    # ------------------------------------------------------------------
    def test_agent_reception_inexistant_retourne_une_erreur_explicite(self):
        self.agent.delete()
        User.objects.filter(username='abdoulaye.kone').delete()

        response = self._post(self._payload())

        self.assertEqual(response.status_code, 400)
        self.assertIn('abdoulaye.kone', response.json()['detail'])
        self.assertEqual(LotEntrepot.objects.count(), 0)
        self.assertFalse(Agent.objects.filter(user__username='abdoulaye.kone').exists())

    # ------------------------------------------------------------------
    # 4 / 5. Quantité et prix invalides
    # ------------------------------------------------------------------
    def test_quantite_invalide_retourne_une_erreur(self):
        response = self._post(self._payload(quantite='0'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LotEntrepot.objects.count(), 0)

        response = self._post(self._payload(quantite='-5'))
        self.assertEqual(response.status_code, 400)

    def test_prix_invalide_retourne_une_erreur(self):
        response = self._post(self._payload(prix_cession='-1'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LotEntrepot.objects.count(), 0)

    # ------------------------------------------------------------------
    # 6. Authentification
    # ------------------------------------------------------------------
    def test_authentification_absente_refusee(self):
        response = self._post(self._payload(), api_key=None)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(LotEntrepot.objects.count(), 0)

    def test_authentification_invalide_refusee(self):
        response = self._post(self._payload(), api_key='mauvaise-cle')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(LotEntrepot.objects.count(), 0)

    # ------------------------------------------------------------------
    # 7 / 8. Idempotence
    # ------------------------------------------------------------------
    def test_meme_idempotency_key_deux_fois_ne_cree_qu_un_lot(self):
        payload = self._payload()

        premiere = self._post(payload)
        self.assertEqual(premiere.status_code, 201)
        self.assertEqual(premiere.json()['status'], 'created')

        deuxieme = self._post(payload)
        self.assertEqual(deuxieme.status_code, 200)
        self.assertEqual(deuxieme.json()['status'], 'already_exists')
        self.assertEqual(deuxieme.json()['lot_id'], premiere.json()['lot_id'])

        self.assertEqual(LotEntrepot.objects.count(), 1)
        self.assertEqual(MouvementStock.objects.count(), 1)

    def test_deux_cessions_differentes_donnent_deux_lots(self):
        self._post(self._payload())
        self._post(self._payload())

        self.assertEqual(LotEntrepot.objects.count(), 2)
        self.assertEqual(MouvementStock.objects.count(), 2)

    # ------------------------------------------------------------------
    # 10. Mouvement de stock
    # ------------------------------------------------------------------
    def test_mouvement_de_stock_reception_est_cree(self):
        response = self._post(self._payload())
        lot = LotEntrepot.objects.get(pk=response.json()['lot_id'])

        mouvement = MouvementStock.objects.get(lot=lot)
        self.assertEqual(mouvement.type_mouvement, 'RECEPTION')
        self.assertEqual(mouvement.produit, lot.produit)
        self.assertEqual(mouvement.quantite, lot.quantite_initiale)
        self.assertEqual(mouvement.date_mouvement, lot.date_reception)

    # ------------------------------------------------------------------
    # 11. Aucune Vente / DetailDistribution créée
    # ------------------------------------------------------------------
    def test_aucune_vente_ni_distribution_creee(self):
        from core.models import DetailDistribution

        self._post(self._payload())

        self.assertEqual(Vente.objects.count(), 0)
        self.assertEqual(DetailDistribution.objects.count(), 0)

    # ------------------------------------------------------------------
    # Fournisseur dédié réutilisé, jamais dupliqué
    # ------------------------------------------------------------------
    def test_fournisseur_champ_dams_reutilise_get_or_create(self):
        Fournisseur.objects.create(nom='Champ DAMS')

        self._post(self._payload())
        self._post(self._payload())

        self.assertEqual(Fournisseur.objects.filter(nom='Champ DAMS').count(), 1)


class CorrectionLotServiceTests(TestCase):
    """sprint-13 — correction administrative d'un LotEntrepot."""

    def setUp(self):
        self.produit = Produit.objects.create(nom='mil')
        self.utilisateur = User.objects.create_user(username='mdmaiga', password='x')
        self.lot = LotEntrepot.objects.create(
            produit=self.produit,
            quantite_initiale=Decimal('100.00'),
            quantite_restante=Decimal('100.00'),
            prix_achat_unitaire=Decimal('250.00'),
        )

    def test_corrige_quantite_et_recalcule_valeur_stock(self):
        CorrectionLotService.corriger_lot(
            self.lot.id,
            quantite_initiale=Decimal('120.00'),
            motif='Erreur de saisie du gestionnaire de stock',
            utilisateur=self.utilisateur,
        )
        self.lot.refresh_from_db()

        self.assertEqual(self.lot.quantite_initiale, Decimal('120.00'))
        self.assertEqual(self.lot.quantite_restante, Decimal('120.00'))
        self.assertEqual(self.lot.valeur_stock_initiale, Decimal('120.00') * Decimal('250.00'))

        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'LOT_QUANTITE')
        self.assertEqual(correction.utilisateur, self.utilisateur)
        self.assertTrue(correction.motif)
        self.assertEqual(correction.anciennes_valeurs['quantite_initiale'], '100.00')
        self.assertEqual(correction.nouvelles_valeurs['quantite_initiale'], '120.00')

    def test_refuse_quantite_sous_ce_qui_est_deja_distribue(self):
        self.lot.quantite_restante = Decimal('10.00')
        self.lot.save()

        with self.assertRaises(ValidationError):
            CorrectionLotService.corriger_lot(
                self.lot.id,
                quantite_initiale=Decimal('50.00'),
                motif='test',
                utilisateur=self.utilisateur,
            )
        self.assertEqual(CorrectionAdministrative.objects.count(), 0)

    def test_motif_obligatoire(self):
        with self.assertRaises(ValidationError):
            CorrectionLotService.corriger_lot(
                self.lot.id,
                quantite_initiale=Decimal('120.00'),
                motif='   ',
                utilisateur=self.utilisateur,
            )

    def test_prix_corrige_est_repercute(self):
        CorrectionLotService.corriger_lot(
            self.lot.id,
            prix_achat_unitaire=Decimal('300.00'),
            motif='Prix erroné annoncé par le fournisseur',
            utilisateur=self.utilisateur,
        )
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.prix_achat_unitaire, Decimal('300.00'))
        self.assertEqual(
            CorrectionAdministrative.objects.get().type_correction, 'LOT_PRIX'
        )


class CorrectionDistributionServiceTests(TestCase):
    """sprint-13 — correction administrative d'une distribution (agent,
    superviseur, quantité)."""

    def setUp(self):
        produit = Produit.objects.create(nom='riz')
        self.utilisateur = User.objects.create_user(username='mdmaiga', password='x')

        sup_user = User.objects.create_user(username='sup1', password='x')
        self.superviseur = Agent.objects.create(user=sup_user, type_agent='entrepot')

        agent_user = User.objects.create_user(username='agent1', password='x')
        self.agent = Agent.objects.create(
            user=agent_user, type_agent='terrain', superviseur=self.superviseur
        )
        agent2_user = User.objects.create_user(username='agent2', password='x')
        self.agent2 = Agent.objects.create(
            user=agent2_user, type_agent='terrain', superviseur=self.superviseur
        )

        self.lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=Decimal('200.00'),
            quantite_restante=Decimal('150.00'),
            prix_achat_unitaire=Decimal('100.00'),
        )
        self.affectation = AffectationLotSuperviseur.objects.create(
            lot=self.lot,
            superviseur=self.superviseur,
            quantite_initiale=Decimal('50.00'),
            quantite_restante=Decimal('0.00'),
            agent_terrain_direct=self.agent,
            date_affectation=date.today(),
        )
        self.distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.agent,
            quantite_totale=Decimal('50.00'),
        )
        self.detail = DetailDistribution.objects.create(
            distribution=self.distribution, lot=self.lot, quantite=Decimal('50.00')
        )

    def test_corrige_quantite_et_cascade_vers_lot_et_affectation(self):
        CorrectionDistributionService.corriger_distribution(
            self.detail.id,
            quantite=Decimal('40.00'),
            motif='Le gestionnaire de stock a trop distribué',
            utilisateur=self.utilisateur,
        )
        self.detail.refresh_from_db()
        self.lot.refresh_from_db()
        self.affectation.refresh_from_db()

        self.assertEqual(self.detail.quantite, Decimal('40.00'))
        self.assertEqual(self.affectation.quantite_initiale, Decimal('40.00'))
        self.assertEqual(self.lot.quantite_restante, Decimal('160.00'))

        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'DISTRIBUTION_QUANTITE')

    def test_refuse_quantite_sous_les_ventes_deja_enregistrees(self):
        Vente.objects.create(
            agent=self.agent,
            detail_distribution=self.detail,
            quantite=Decimal('30.00'),
            prix_vente_unitaire=Decimal('150.00'),
            type_vente='detail',
        )
        with self.assertRaises(ValidationError):
            CorrectionDistributionService.corriger_distribution(
                self.detail.id,
                quantite=Decimal('20.00'),
                motif='test',
                utilisateur=self.utilisateur,
            )

    def test_change_agent_au_sein_du_meme_superviseur(self):
        CorrectionDistributionService.corriger_distribution(
            self.detail.id,
            agent_terrain=self.agent2,
            motif='Le gestionnaire de stock s\'est trompé d\'agent',
            utilisateur=self.utilisateur,
        )
        self.distribution.refresh_from_db()
        self.assertEqual(self.distribution.agent_terrain_id, self.agent2.id)

        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'DISTRIBUTION_AGENT')

    def test_refuse_agent_non_rattache_au_superviseur(self):
        sup3_user = User.objects.create_user(username='sup3', password='x')
        superviseur3 = Agent.objects.create(user=sup3_user, type_agent='entrepot')
        agent3_user = User.objects.create_user(username='agent3', password='x')
        agent3 = Agent.objects.create(
            user=agent3_user, type_agent='terrain', superviseur=superviseur3
        )

        with self.assertRaises(ValidationError):
            CorrectionDistributionService.corriger_distribution(
                self.detail.id,
                agent_terrain=agent3,
                motif='test',
                utilisateur=self.utilisateur,
            )

    def test_motif_obligatoire(self):
        with self.assertRaises(ValidationError):
            CorrectionDistributionService.corriger_distribution(
                self.detail.id,
                quantite=Decimal('40.00'),
                motif='',
                utilisateur=self.utilisateur,
            )
