from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Agent,
    Alerte,
    DetailDistribution,
    DistributionAgent,
    LotEntrepot,
    Produit,
    Recouvrement,
    RecouvrementSuperviseur,
    Vente,
)
from finance.services import DATE_DEBUT_FINANCE
from monitoring.services.deduplication_service import AlerteDeduplicationService
from monitoring.services.moteur_alerte import AlerteMoteur


class AlerteDeduplicationServiceTestCase(TestCase):
    def setUp(self):
        self.produit = Produit.objects.create(nom="Riz")
        self.lot = LotEntrepot.objects.create(
            produit=self.produit,
            quantite_initiale=100,
            quantite_restante=50,
            prix_achat_unitaire=1000,
        )

    def test_creation_initiale_alerte(self):
        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="stock",
            defaults={"niveau": "warning", "message": "Lot dormant."},
            lot=self.lot,
        )

        self.assertTrue(cree)
        self.assertTrue(doit_envoyer)
        self.assertEqual(alerte.statut, "ACTIVE")
        self.assertEqual(alerte.nombre_envois, 1)
        self.assertIsNotNone(alerte.date_dernier_envoi)

    def test_pas_de_doublon_si_alerte_active_existe(self):
        AlerteDeduplicationService.get_ou_creer(
            type_alerte="stock",
            defaults={"niveau": "warning", "message": "Lot dormant."},
            lot=self.lot,
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="stock",
            defaults={"niveau": "warning", "message": "Lot dormant."},
            lot=self.lot,
        )

        self.assertFalse(cree)
        self.assertFalse(doit_envoyer)
        self.assertEqual(Alerte.objects.filter(type_alerte="stock", lot=self.lot).count(), 1)

    def test_renvoi_apres_delai_ecoule(self):
        # type "solde" : reenvoi_heures=24 (monitoring/constants.py)
        existante = Alerte.objects.create(
            type_alerte="solde",
            niveau="info",
            message="Solde superviseur.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now() - timedelta(hours=25),
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="solde",
            defaults={"niveau": "info", "message": "Solde superviseur."},
            lot=self.lot,
        )

        self.assertFalse(cree)
        self.assertTrue(doit_envoyer)
        alerte.refresh_from_db()
        self.assertEqual(alerte.pk, existante.pk)
        self.assertEqual(alerte.nombre_envois, 2)

    def test_silence_avant_delai(self):
        Alerte.objects.create(
            type_alerte="solde",
            niveau="info",
            message="Solde superviseur.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now() - timedelta(hours=1),
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="solde",
            defaults={"niveau": "info", "message": "Solde superviseur."},
            lot=self.lot,
        )

        self.assertFalse(cree)
        self.assertFalse(doit_envoyer)
        self.assertEqual(alerte.nombre_envois, 1)

    def test_cloture_automatique_si_situation_disparue(self):
        Alerte.objects.create(
            type_alerte="stock",
            niveau="warning",
            message="Lot dormant.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        AlerteDeduplicationService.cloturer_si_resolue("stock", [])

        alerte = Alerte.objects.get(type_alerte="stock", lot=self.lot)
        self.assertEqual(alerte.statut, "RESOLUE")
        self.assertIsNotNone(alerte.date_resolution)

    def test_message_rafraichi_meme_sans_renvoi(self):
        # type "stock" : reenvoi_heures=None (silence tant qu'ACTIVE)
        Alerte.objects.create(
            type_alerte="stock",
            niveau="warning",
            message="Ancien message.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="stock",
            defaults={"niveau": "warning", "message": "Message à jour avec les derniers chiffres."},
            lot=self.lot,
        )

        self.assertFalse(cree)
        self.assertFalse(doit_envoyer)
        alerte.refresh_from_db()
        self.assertEqual(alerte.message, "Message à jour avec les derniers chiffres.")
        self.assertEqual(alerte.nombre_envois, 1)

    def test_pas_de_cloture_si_situation_toujours_active(self):
        Alerte.objects.create(
            type_alerte="stock",
            niveau="warning",
            message="Lot dormant.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        AlerteDeduplicationService.cloturer_si_resolue("stock", [{"lot": self.lot}])

        alerte = Alerte.objects.get(type_alerte="stock", lot=self.lot)
        self.assertEqual(alerte.statut, "ACTIVE")


class AlerteMoteurTestCase(TestCase):
    """
    Note sur les dates "finance" : DATE_DEBUT_FINANCE (finance/services.py) est fixée
    au 2026-08-01, une date future par rapport à l'exécution réelle de ces tests
    (2026-07-27). `solde_superviseur()`/`lister_soldes_superviseurs()` utilisent
    `timezone.localdate()` ("aujourd'hui") par défaut comme borne haute — sans figer
    "aujourd'hui" après DATE_DEBUT_FINANCE, la fenêtre [DATE_DEBUT_FINANCE, aujourd'hui]
    est vide et aucun Recouvrement ne peut jamais être compté. On fige donc
    `timezone.localdate()` uniquement pour les tests de la règle "solde" (1a/1b) via
    `mock.patch`, seule façon de tester cette règle avant la vraie date de bascule.
    """

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
        self.rot = Agent.objects.create(
            user=User.objects.create_user(username="rot"),
            type_agent="rot",
        )
        # Empêche tout appel réseau réel vers l'API Telegram pendant les tests,
        # même si TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID sont renseignés en .env.
        patcher = mock.patch("monitoring.providers.telegram.requests.post")
        self.addCleanup(patcher.stop)
        patcher.start()

    def _lot(self, quantite_initiale, quantite_restante, date_reception, prix_achat_unitaire=1000):
        return LotEntrepot.objects.create(
            produit=self.produit,
            quantite_initiale=quantite_initiale,
            quantite_restante=quantite_restante,
            prix_achat_unitaire=prix_achat_unitaire,
            date_reception=date_reception,
        )

    def _distribution(self, date_distribution):
        return DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.agent_terrain,
            date_distribution=date_distribution,
        )

    # -- Règle "solde" (1a) et "solde_persistant" (1b) --------------------

    def test_evaluer_solde_superviseur_cree_alerte_routine(self):
        Recouvrement.objects.create(
            agent=self.agent_terrain,
            superviseur=self.superviseur,
            montant_recouvre=Decimal("50000"),
            date_recouvrement=timezone.make_aware(
                timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=1), timezone.datetime.min.time())
            ),
        )

        with mock.patch("finance.services.timezone.localdate", return_value=DATE_DEBUT_FINANCE + timedelta(days=5)):
            AlerteMoteur.evaluer_solde_superviseur()

        self.assertTrue(
            Alerte.objects.filter(
                type_alerte="solde", superviseur=self.superviseur.user, statut="ACTIVE"
            ).exists()
        )

    def test_evaluer_solde_superviseur_resolution_sous_seuil(self):
        recouvrement = Recouvrement.objects.create(
            agent=self.agent_terrain,
            superviseur=self.superviseur,
            montant_recouvre=Decimal("50000"),
            date_recouvrement=timezone.make_aware(
                timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=1), timezone.datetime.min.time())
            ),
        )

        with mock.patch("finance.services.timezone.localdate", return_value=DATE_DEBUT_FINANCE + timedelta(days=5)):
            AlerteMoteur.evaluer_solde_superviseur()
            self.assertTrue(
                Alerte.objects.filter(
                    type_alerte="solde", superviseur=self.superviseur.user, statut="ACTIVE"
                ).exists()
            )

            # La situation disparaît : le superviseur remet tout au ROT.
            RecouvrementSuperviseur.objects.create(
                superviseur=self.superviseur,
                rot=self.rot,
                montant=Decimal("50000"),
                date_recouvrement=timezone.make_aware(
                    timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=2), timezone.datetime.min.time())
                ),
            )
            AlerteMoteur.evaluer_solde_superviseur()

        alerte = Alerte.objects.get(type_alerte="solde", superviseur=self.superviseur.user)
        self.assertEqual(alerte.statut, "RESOLUE")

    def test_solde_persistant_avec_3_cycles_residuels(self):
        Recouvrement.objects.create(
            agent=self.agent_terrain,
            superviseur=self.superviseur,
            montant_recouvre=Decimal("100000"),
            date_recouvrement=timezone.make_aware(
                timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=1), timezone.datetime.min.time())
            ),
        )
        for jour in (2, 3, 4):
            RecouvrementSuperviseur.objects.create(
                superviseur=self.superviseur,
                rot=self.rot,
                montant=Decimal("10000"),
                date_recouvrement=timezone.make_aware(
                    timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=jour), timezone.datetime.min.time())
                ),
            )

        with mock.patch("finance.services.timezone.localdate", return_value=DATE_DEBUT_FINANCE + timedelta(days=10)):
            AlerteMoteur.evaluer_solde_superviseur()

        self.assertTrue(
            Alerte.objects.filter(
                type_alerte="solde_persistant", superviseur=self.superviseur.user, statut="ACTIVE"
            ).exists()
        )

    def test_pas_de_solde_persistant_avec_2_cycles(self):
        Recouvrement.objects.create(
            agent=self.agent_terrain,
            superviseur=self.superviseur,
            montant_recouvre=Decimal("100000"),
            date_recouvrement=timezone.make_aware(
                timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=1), timezone.datetime.min.time())
            ),
        )
        for jour in (2, 3):
            RecouvrementSuperviseur.objects.create(
                superviseur=self.superviseur,
                rot=self.rot,
                montant=Decimal("10000"),
                date_recouvrement=timezone.make_aware(
                    timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=jour), timezone.datetime.min.time())
                ),
            )

        with mock.patch("finance.services.timezone.localdate", return_value=DATE_DEBUT_FINANCE + timedelta(days=10)):
            AlerteMoteur.evaluer_solde_superviseur()

        self.assertFalse(
            Alerte.objects.filter(
                type_alerte="solde_persistant", superviseur=self.superviseur.user
            ).exists()
        )

    # -- Règle "stock" ------------------------------------------------------

    def test_evaluer_stock_ancien_cree_alerte(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=20))

        AlerteMoteur.evaluer_stock_ancien()

        self.assertTrue(Alerte.objects.filter(type_alerte="stock", lot=lot, statut="ACTIVE").exists())

    def test_evaluer_stock_ancien_resolution_quand_lot_epuise(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=20))
        AlerteMoteur.evaluer_stock_ancien()
        self.assertTrue(Alerte.objects.filter(type_alerte="stock", lot=lot, statut="ACTIVE").exists())

        lot.quantite_restante = 0
        lot.save(update_fields=["quantite_restante"])
        AlerteMoteur.evaluer_stock_ancien()

        alerte = Alerte.objects.get(type_alerte="stock", lot=lot)
        self.assertEqual(alerte.statut, "RESOLUE")

    # -- Règle "prix" ---------------------------------------------------------

    def test_evaluer_variation_prix_cree_alerte(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=1), prix_achat_unitaire=1000)
        distribution = self._distribution(timezone.now() - timedelta(days=1))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1000,  # marge nulle < SEUIL_MARGE_MINIMALE (45)
            date_vente=timezone.now(),
        )

        AlerteMoteur.evaluer_variation_prix()

        self.assertTrue(Alerte.objects.filter(type_alerte="prix", lot=lot, statut="ACTIVE").exists())

    # -- Règle "activite" -----------------------------------------------------

    def test_evaluer_baisse_activite_cree_alerte_avec_distribution_hydratee(self):
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

        AlerteMoteur.evaluer_baisse_activite()

        alerte = Alerte.objects.get(type_alerte="activite", agent=self.agent_terrain.user, statut="ACTIVE")
        self.assertEqual(alerte.distribution, detail)

    def test_evaluer_baisse_activite_ignore_un_superviseur(self):
        # Un superviseur (type_agent="entrepot") vend parfois directement sur le
        # terrain — occasionnel, ce n'est pas son activité principale : pas
        # d'alerte "baisse d'activité" pour lui.
        lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.superviseur,
            date_distribution=timezone.now() - timedelta(days=5),
        )
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.superviseur,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(days=3),
        )

        AlerteMoteur.evaluer_baisse_activite()

        self.assertFalse(
            Alerte.objects.filter(type_alerte="activite", agent=self.superviseur.user).exists()
        )

    def test_evaluer_baisse_activite_resolution_agent_qui_recommence_a_vendre(self):
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
        AlerteMoteur.evaluer_baisse_activite()
        self.assertTrue(
            Alerte.objects.filter(type_alerte="activite", agent=self.agent_terrain.user, statut="ACTIVE").exists()
        )

        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=5,
            prix_vente_unitaire=1200,
            date_vente=timezone.now(),
        )
        AlerteMoteur.evaluer_baisse_activite()

        alerte = Alerte.objects.get(type_alerte="activite", agent=self.agent_terrain.user)
        self.assertEqual(alerte.statut, "RESOLUE")
