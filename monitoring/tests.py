from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Agent,
    AffectationLotSuperviseur,
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
    """Mécanique générique de déduplication — indépendante du type_alerte
    utilisé (« stock » sert ici de type d'exemple quelconque)."""

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
            type_alerte="stock_entrepot",
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
            type_alerte="stock_entrepot",
            defaults={"niveau": "warning", "message": "Lot dormant."},
            lot=self.lot,
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="stock_entrepot",
            defaults={"niveau": "warning", "message": "Lot dormant."},
            lot=self.lot,
        )

        self.assertFalse(cree)
        self.assertFalse(doit_envoyer)
        self.assertEqual(Alerte.objects.filter(type_alerte="stock_entrepot", lot=self.lot).count(), 1)

    def test_renvoi_apres_delai_ecoule(self):
        # type "solde" : reenvoi_heures=24 (monitoring/constants.py)
        existante = Alerte.objects.create(
            type_alerte="solde",
            niveau="info",
            message="Solde superviseur.",
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now() - timedelta(hours=25),
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="solde",
            defaults={"niveau": "info", "message": "Solde superviseur."},
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
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now() - timedelta(hours=1),
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="solde",
            defaults={"niveau": "info", "message": "Solde superviseur."},
        )

        self.assertFalse(cree)
        self.assertFalse(doit_envoyer)
        self.assertEqual(alerte.nombre_envois, 1)

    def test_cloture_automatique_si_situation_disparue(self):
        Alerte.objects.create(
            type_alerte="stock_entrepot",
            niveau="warning",
            message="Lot dormant.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        AlerteDeduplicationService.cloturer_si_resolue("stock_entrepot", [])

        alerte = Alerte.objects.get(type_alerte="stock_entrepot", lot=self.lot)
        self.assertEqual(alerte.statut, "RESOLUE")
        self.assertIsNotNone(alerte.date_resolution)

    def test_message_rafraichi_meme_sans_renvoi(self):
        # type "prix" : reenvoi_heures=None (silence tant qu'ACTIVE)
        Alerte.objects.create(
            type_alerte="prix",
            niveau="critique",
            message="Ancien message.",
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        alerte, cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
            type_alerte="prix",
            defaults={"niveau": "critique", "message": "Message à jour avec les derniers chiffres."},
        )

        self.assertFalse(cree)
        self.assertFalse(doit_envoyer)
        alerte.refresh_from_db()
        self.assertEqual(alerte.message, "Message à jour avec les derniers chiffres.")
        self.assertEqual(alerte.nombre_envois, 1)

    def test_pas_de_cloture_si_situation_toujours_active(self):
        Alerte.objects.create(
            type_alerte="stock_entrepot",
            niveau="warning",
            message="Lot dormant.",
            lot=self.lot,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        AlerteDeduplicationService.cloturer_si_resolue("stock_entrepot", [{"lot": self.lot}])

        alerte = Alerte.objects.get(type_alerte="stock_entrepot", lot=self.lot)
        self.assertEqual(alerte.statut, "ACTIVE")

    def test_cloture_avec_champ_cle_ne_contamine_pas_l_autre_famille(self):
        # champ_cle : mécanisme réutilisable si un type_alerte devait un jour
        # mélanger plusieurs familles de clés (aucune règle actuelle ne le
        # fait — chaque règle agrégée n'utilise plus qu'une seule Alerte par
        # type, sans clé d'identification — mais le garde-fou reste testé).
        superviseur_user = User.objects.create_user(username="superviseur_dedup")
        agent_user = User.objects.create_user(username="agent_dedup")

        Alerte.objects.create(
            type_alerte="solde_persistant",
            niveau="critique",
            message="Groupé superviseur.",
            superviseur=superviseur_user,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )
        Alerte.objects.create(
            type_alerte="solde_persistant",
            niveau="critique",
            message="Agent individuel.",
            agent=agent_user,
            statut="ACTIVE",
            nombre_envois=1,
            date_dernier_envoi=timezone.now(),
        )

        AlerteDeduplicationService.cloturer_si_resolue("solde_persistant", [], champ_cle="superviseur")

        self.assertEqual(
            Alerte.objects.get(type_alerte="solde_persistant", superviseur=superviseur_user).statut, "RESOLUE"
        )
        self.assertEqual(
            Alerte.objects.get(type_alerte="solde_persistant", agent=agent_user).statut, "ACTIVE"
        )


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

    Depuis la refonte des alertes (2026-08-13), chaque règle diffuse au plus UN message Telegram par
    évaluation (Alerte unique par type_alerte, sans clé d'identification) —
    les assertions vérifient donc le contenu du message plutôt qu'une Alerte
    par superviseur/agent/lot.
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

    def _distribution(self, date_distribution, agent_terrain=None):
        return DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=agent_terrain or self.agent_terrain,
            date_distribution=date_distribution,
        )

    def _vente(self, agent, detail, quantite, prix_vente_unitaire, date_vente):
        return Vente.objects.create(
            agent=agent,
            detail_distribution=detail,
            quantite=quantite,
            prix_vente_unitaire=prix_vente_unitaire,
            date_vente=date_vente,
        )

    # -- Règle "solde" (1a) et "solde_persistant" (1b) --------------------

    def test_evaluer_solde_superviseur_cree_alerte_agregee(self):
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

        alerte = Alerte.objects.get(type_alerte="solde", statut="ACTIVE")
        self.assertIsNone(alerte.superviseur)
        self.assertIn(self.superviseur.full_name, alerte.message)
        self.assertIn("SOLDES SUPERVISEURS", alerte.message)

    def test_evaluer_solde_superviseur_liste_plusieurs_superviseurs_dans_le_meme_message(self):
        autre_superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur_2"),
            type_agent="entrepot",
        )
        autre_agent = Agent.objects.create(
            user=User.objects.create_user(username="agent_terrain_2"),
            type_agent="terrain",
            superviseur=autre_superviseur,
        )
        for superviseur, agent in ((self.superviseur, self.agent_terrain), (autre_superviseur, autre_agent)):
            Recouvrement.objects.create(
                agent=agent,
                superviseur=superviseur,
                montant_recouvre=Decimal("50000"),
                date_recouvrement=timezone.make_aware(
                    timezone.datetime.combine(DATE_DEBUT_FINANCE + timedelta(days=1), timezone.datetime.min.time())
                ),
            )

        with mock.patch("finance.services.timezone.localdate", return_value=DATE_DEBUT_FINANCE + timedelta(days=5)):
            AlerteMoteur.evaluer_solde_superviseur()

        self.assertEqual(Alerte.objects.filter(type_alerte="solde", statut="ACTIVE").count(), 1)
        alerte = Alerte.objects.get(type_alerte="solde", statut="ACTIVE")
        self.assertIn(self.superviseur.full_name, alerte.message)
        self.assertIn(autre_superviseur.full_name, alerte.message)

    def test_evaluer_solde_superviseur_resolution_sous_seuil(self):
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
            self.assertTrue(Alerte.objects.filter(type_alerte="solde", statut="ACTIVE").exists())

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

        alerte = Alerte.objects.get(type_alerte="solde")
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

    # -- Règle "stock ancien" : 3 messages distincts -------------------------

    def test_evaluer_stock_ancien_entrepot_cree_alerte(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=20))

        AlerteMoteur.evaluer_stock_ancien()

        alerte = Alerte.objects.get(type_alerte="stock_entrepot", statut="ACTIVE")
        self.assertIn(lot.produit.nom, alerte.message)
        self.assertIn("ENTREPÔT", alerte.message)

    def test_evaluer_stock_ancien_entrepot_resolution_quand_lot_epuise(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=20))
        AlerteMoteur.evaluer_stock_ancien()
        self.assertTrue(Alerte.objects.filter(type_alerte="stock_entrepot", statut="ACTIVE").exists())

        lot.quantite_restante = 0
        lot.save(update_fields=["quantite_restante"])
        AlerteMoteur.evaluer_stock_ancien()

        alerte = Alerte.objects.get(type_alerte="stock_entrepot")
        self.assertEqual(alerte.statut, "RESOLUE")

    def test_evaluer_stock_ancien_superviseur_groupe(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=1))
        AffectationLotSuperviseur.objects.create(
            lot=lot,
            superviseur=self.superviseur,
            quantite_initiale=30,
            quantite_restante=30,
            attribue_par=self.rot,
            date_affectation=date.today() - timedelta(days=3),
        )

        AlerteMoteur.evaluer_stock_ancien()

        alerte = Alerte.objects.get(type_alerte="stock_superviseur", statut="ACTIVE")
        self.assertIn(self.superviseur.full_name, alerte.message)
        self.assertIn(lot.produit.nom, alerte.message)
        self.assertFalse(Alerte.objects.filter(type_alerte="stock_entrepot").exists())

    def test_evaluer_stock_ancien_superviseur_moins_de_3_jours_absent(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=1))
        AffectationLotSuperviseur.objects.create(
            lot=lot,
            superviseur=self.superviseur,
            quantite_initiale=30,
            quantite_restante=30,
            attribue_par=self.rot,
            date_affectation=date.today() - timedelta(days=2),
        )

        AlerteMoteur.evaluer_stock_ancien()

        self.assertFalse(Alerte.objects.filter(type_alerte="stock_superviseur").exists())

    def test_evaluer_stock_ancien_agents_groupe_par_superviseur_puis_agent(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=3))
        distribution = self._distribution(timezone.now() - timedelta(days=3))
        DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=20)

        AlerteMoteur.evaluer_stock_ancien()

        alerte = Alerte.objects.get(type_alerte="stock_agent", statut="ACTIVE")
        self.assertIn(self.superviseur.full_name, alerte.message)
        self.assertIn(self.agent_terrain.full_name, alerte.message)
        self.assertIn(lot.produit.nom, alerte.message)

    # -- Règle "prix" (ventes sous la marge minimale) ------------------------

    def test_evaluer_variation_prix_marge_sous_seuil_cree_alerte(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=1), prix_achat_unitaire=1000)
        distribution = self._distribution(timezone.now() - timedelta(days=1))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(self.agent_terrain, detail, 10, prix_vente_unitaire=1010, date_vente=timezone.now())
        # Marge = 10 FCFA < 25 : anomalie.

        AlerteMoteur.evaluer_variation_prix()

        alerte = Alerte.objects.get(type_alerte="prix", statut="ACTIVE")
        self.assertIn(self.superviseur.full_name, alerte.message)
        self.assertIn(self.agent_terrain.full_name, alerte.message)
        self.assertIn("MARGE MINIMALE", alerte.message)

    def test_evaluer_variation_prix_marge_exactement_au_seuil_pas_d_alerte(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=1), prix_achat_unitaire=1000)
        distribution = self._distribution(timezone.now() - timedelta(days=1))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(self.agent_terrain, detail, 10, prix_vente_unitaire=1045, date_vente=timezone.now())
        # Marge = 45 FCFA == seuil (SEUIL_MARGE_MINIMALE) : pas d'anomalie ("marge >= seuil → pas d'alerte").

        AlerteMoteur.evaluer_variation_prix()

        self.assertFalse(Alerte.objects.filter(type_alerte="prix", statut="ACTIVE").exists())

    def test_evaluer_variation_prix_marge_au_dessus_du_seuil_pas_d_alerte(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=1), prix_achat_unitaire=1000)
        distribution = self._distribution(timezone.now() - timedelta(days=1))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(self.agent_terrain, detail, 10, prix_vente_unitaire=1100, date_vente=timezone.now())

        AlerteMoteur.evaluer_variation_prix()

        self.assertFalse(Alerte.objects.filter(type_alerte="prix", statut="ACTIVE").exists())

    # -- Règle "activite" (dernière vente globale de l'agent) ----------------

    def test_evaluer_baisse_activite_groupe_par_superviseur(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        distribution = self._distribution(timezone.now() - timedelta(days=10))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(self.agent_terrain, detail, 10, 1200, timezone.now() - timedelta(days=6))

        AlerteMoteur.evaluer_baisse_activite()

        alerte = Alerte.objects.get(type_alerte="activite", statut="ACTIVE")
        self.assertIn(self.superviseur.full_name, alerte.message)
        self.assertIn(self.agent_terrain.full_name, alerte.message)
        self.assertNotIn("AGENTS SANS SUPERVISEUR", alerte.message)

    def test_evaluer_baisse_activite_agent_sans_superviseur_section_distincte(self):
        agent_sans_superviseur = Agent.objects.create(
            user=User.objects.create_user(username="agent_orphelin"),
            type_agent="terrain",
        )
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=agent_sans_superviseur,
            date_distribution=timezone.now() - timedelta(days=10),
        )
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(agent_sans_superviseur, detail, 10, 1200, timezone.now() - timedelta(days=6))

        AlerteMoteur.evaluer_baisse_activite()

        alerte = Alerte.objects.get(type_alerte="activite", statut="ACTIVE")
        self.assertIn("AGENTS SANS SUPERVISEUR", alerte.message)
        self.assertIn(agent_sans_superviseur.full_name, alerte.message)

    def test_evaluer_baisse_activite_ignore_un_superviseur(self):
        # Un superviseur (type_agent="entrepot") vend parfois directement sur le
        # terrain — occasionnel, ce n'est pas son activité principale : il
        # n'entre pas dans le calcul "agents de vente".
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.superviseur,
            date_distribution=timezone.now() - timedelta(days=10),
        )
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(self.superviseur, detail, 10, 1200, timezone.now() - timedelta(days=8))

        AlerteMoteur.evaluer_baisse_activite()

        self.assertFalse(Alerte.objects.filter(type_alerte="activite", statut="ACTIVE").exists())

    def test_evaluer_baisse_activite_vente_recente_sur_lot_different_pas_d_alerte(self):
        # Bug historique corrigé (2026-08-13) : une distribution ancienne sans vente
        # sur SON lot ne doit plus déclencher d'alerte si l'agent a vendu
        # récemment sur un autre lot.
        vieux_lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        vieille_distribution = self._distribution(timezone.now() - timedelta(days=10))
        DetailDistribution.objects.create(distribution=vieille_distribution, lot=vieux_lot, quantite=100)

        nouveau_lot = self._lot(100, 50, timezone.now() - timedelta(days=2))
        nouvelle_distribution = self._distribution(timezone.now() - timedelta(days=2))
        nouveau_detail = DetailDistribution.objects.create(
            distribution=nouvelle_distribution, lot=nouveau_lot, quantite=100
        )
        self._vente(self.agent_terrain, nouveau_detail, 10, 1200, timezone.now() - timedelta(hours=1))

        AlerteMoteur.evaluer_baisse_activite()

        self.assertFalse(Alerte.objects.filter(type_alerte="activite", statut="ACTIVE").exists())

    def test_evaluer_baisse_activite_resolution_agent_qui_recommence_a_vendre(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        distribution = self._distribution(timezone.now() - timedelta(days=10))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        self._vente(self.agent_terrain, detail, 10, 1200, timezone.now() - timedelta(days=6))

        AlerteMoteur.evaluer_baisse_activite()
        self.assertTrue(Alerte.objects.filter(type_alerte="activite", statut="ACTIVE").exists())

        self._vente(self.agent_terrain, detail, 5, 1200, timezone.now())
        AlerteMoteur.evaluer_baisse_activite()

        alerte = Alerte.objects.get(type_alerte="activite")
        self.assertEqual(alerte.statut, "RESOLUE")
