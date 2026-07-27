from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import (
    AffectationLotSuperviseur,
    Agent,
    DetailDistribution,
    DistributionAgent,
    LotEntrepot,
    Produit,
    Vente,
)
from surveillance.services.stock_age_service import StockAgeService


class StockAgeServiceTestCase(TestCase):
    def setUp(self):
        self.produit = Produit.objects.create(nom="Riz")

        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur"),
            type_agent="entrepot",
        )
        self.agent_terrain = Agent.objects.create(
            user=User.objects.create_user(username="agent_terrain"),
            type_agent="terrain",
            superviseur=self.superviseur,
        )

    def _lot(self, quantite_initiale, quantite_restante, date_reception):
        return LotEntrepot.objects.create(
            produit=self.produit,
            quantite_initiale=quantite_initiale,
            quantite_restante=quantite_restante,
            prix_achat_unitaire=1000,
            date_reception=date_reception,
        )

    def _distribution(self, date_distribution):
        return DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.agent_terrain,
            date_distribution=date_distribution,
        )

    def test_agent_avec_vente_recente_absent(self):
        lot = self._lot(100, 0, timezone.now() - timedelta(days=5))
        distribution = self._distribution(timezone.now() - timedelta(days=5))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(hours=1),
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(resultats, [])
        self.assertEqual(StockAgeService.count_agents_sans_vente_recente(), 0)

    def test_agent_sans_vente_depuis_plus_de_deux_jours_present(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
        distribution = self._distribution(timezone.now() - timedelta(days=5))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(days=3),
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["agent"], self.agent_terrain)
        self.assertEqual(StockAgeService.count_agents_sans_vente_recente(), 1)

    def test_vente_supprimee_ignoree_pour_la_derniere_vente(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
        distribution = self._distribution(timezone.now() - timedelta(days=5))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(hours=1),
            est_supprime=True,
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(len(resultats), 1)

    def test_lot_totalement_distribue_absent_de_stock_dormant(self):
        self._lot(100, 0, timezone.now() - timedelta(days=20))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_lot_partiellement_distribue_depuis_plus_de_14_jours_present(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=20))

        resultats = StockAgeService.lots_stock_dormant()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["lot"], lot)
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 1)

    def test_lot_recent_absent_de_stock_dormant(self):
        self._lot(100, 30, timezone.now() - timedelta(days=5))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_lot_anterieur_au_plancher_stock_exclu(self):
        # 2026-04-01 est antérieur à DATE_PLANCHER_STOCK (2026-05-15) : exclu
        # même si le lot dort depuis largement plus de 14 jours.
        self._lot(100, 30, timezone.make_aware(timezone.datetime(2026, 4, 1)))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def _affectation(self, quantite_initiale, quantite_restante, date_affectation, lot=None):
        return AffectationLotSuperviseur.objects.create(
            lot=lot or self._lot(100, 0, timezone.now() - timedelta(days=20)),
            superviseur=self.superviseur,
            quantite_initiale=quantite_initiale,
            quantite_restante=quantite_restante,
            date_affectation=date_affectation,
        )

    def test_lot_mis_a_disposition_superviseur_depuis_plus_de_14_jours_present(self):
        affectation = self._affectation(100, 40, date.today() - timedelta(days=20))

        resultats = StockAgeService.lots_stock_dormant()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["origine"], "superviseur")
        self.assertEqual(resultats[0]["superviseur"], self.superviseur)
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 1)

    def test_lot_totalement_redistribue_par_superviseur_absent(self):
        self._affectation(100, 0, date.today() - timedelta(days=20))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_affectation_anterieure_au_plancher_stock_exclue(self):
        self._affectation(100, 40, date(2026, 4, 1))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_distribution_anterieure_au_plancher_stock_exclue_de_rotation_lente(self):
        lot = self._lot(100, 50, timezone.make_aware(timezone.datetime(2026, 4, 1)))
        distribution = self._distribution(timezone.make_aware(timezone.datetime(2026, 4, 1)))
        DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(resultats, [])
        self.assertEqual(StockAgeService.count_agents_sans_vente_recente(), 0)

    def test_ligne_rotation_lente_porte_les_ids_pour_suppression(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
        distribution = self._distribution(timezone.now() - timedelta(days=5))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(resultats[0]["distribution_id"], distribution.id)
        self.assertEqual(resultats[0]["detail_distribution_id"], detail.id)
