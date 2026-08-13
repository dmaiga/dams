from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
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
from surveillance.services.comparaison_service import ComparaisonPeriodeService
from surveillance.services.detail_produit_service import DetailProduitService
from surveillance.services.detail_superviseur_service import DetailSuperviseurService
from surveillance.services.stock_age_service import StockAgeService
from surveillance.week_utils import parse_mois


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

    def _distribution(self, date_distribution, agent_terrain=None):
        return DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=agent_terrain or self.agent_terrain,
            date_distribution=date_distribution,
        )

    # -- Activité commerciale (dernière vente globale de l'agent) -----------

    def test_agent_avec_vente_recente_absent(self):
        # Vendu hier : pas d'alerte.
        lot = self._lot(100, 0, timezone.now() - timedelta(days=10))
        distribution = self._distribution(timezone.now() - timedelta(days=10))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(days=1),
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(resultats, [])
        self.assertEqual(StockAgeService.count_agents_sans_vente_recente(), 0)

    def test_agent_sans_vente_depuis_exactement_3_jours_present(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        distribution = self._distribution(timezone.now() - timedelta(days=10))
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

    def test_agent_sans_vente_depuis_plus_de_3_jours_present(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        distribution = self._distribution(timezone.now() - timedelta(days=10))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(days=8),
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["jours_ecoules"], 8)

    def test_agent_jamais_vendu_present(self):
        distribution = self._distribution(timezone.now() - timedelta(days=10))
        DetailDistribution.objects.create(
            distribution=distribution,
            lot=self._lot(100, 50, timezone.now() - timedelta(days=10)),
            quantite=100,
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(len(resultats), 1)
        self.assertIsNone(resultats[0]["derniere_vente"])
        self.assertIsNone(resultats[0]["jours_ecoules"])

    def test_vente_supprimee_ignoree_pour_la_derniere_vente(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        distribution = self._distribution(timezone.now() - timedelta(days=10))
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

    def test_agent_avec_plusieurs_distributions_vente_recente_sur_lot_different(self):
        # Bug historique corrigé (2026-08-13) : une distribution ancienne sans
        # vente sur SON lot ne doit plus déclencher d'alerte si l'agent a
        # vendu récemment sur un AUTRE lot, plus récent.
        vieux_lot = self._lot(100, 50, timezone.now() - timedelta(days=10))
        vieille_distribution = self._distribution(timezone.now() - timedelta(days=10))
        DetailDistribution.objects.create(distribution=vieille_distribution, lot=vieux_lot, quantite=100)

        nouveau_lot = self._lot(100, 50, timezone.now() - timedelta(days=2))
        nouvelle_distribution = self._distribution(timezone.now() - timedelta(days=2))
        nouveau_detail = DetailDistribution.objects.create(
            distribution=nouvelle_distribution, lot=nouveau_lot, quantite=100
        )
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=nouveau_detail,
            quantite=10,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(hours=1),
        )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(resultats, [])

    def test_plusieurs_agents_sous_meme_superviseur(self):
        autre_agent = Agent.objects.create(
            user=User.objects.create_user(username="agent_terrain_2"),
            type_agent="agent_gros",
            superviseur=self.superviseur,
        )
        for agent in (self.agent_terrain, autre_agent):
            distribution = self._distribution(timezone.now() - timedelta(days=10), agent_terrain=agent)
            DetailDistribution.objects.create(
                distribution=distribution,
                lot=self._lot(100, 50, timezone.now() - timedelta(days=10)),
                quantite=100,
            )

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual({r["agent"] for r in resultats}, {self.agent_terrain, autre_agent})
        self.assertTrue(all(r["superviseur"] == self.superviseur for r in resultats))

    def test_distribution_anterieure_au_plancher_stock_exclue(self):
        lot = self._lot(100, 50, timezone.make_aware(timezone.datetime(2026, 4, 1)))
        distribution = self._distribution(timezone.make_aware(timezone.datetime(2026, 4, 1)))
        DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)

        resultats = StockAgeService.agents_sans_vente_recente()

        self.assertEqual(resultats, [])
        self.assertEqual(StockAgeService.count_agents_sans_vente_recente(), 0)

    # -- Stock dormant : entrepôt central (15 jours, inchangé) ---------------

    def test_lot_totalement_distribue_absent_de_stock_dormant(self):
        self._lot(100, 0, timezone.now() - timedelta(days=20))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_lot_partiellement_distribue_depuis_plus_de_14_jours_present(self):
        lot = self._lot(100, 30, timezone.now() - timedelta(days=20))

        resultats = StockAgeService.lots_stock_dormant()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["lot"], lot)
        self.assertEqual(resultats[0]["origine"], "entrepot")
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 1)

    def test_lot_recent_absent_de_stock_dormant(self):
        self._lot(100, 30, timezone.now() - timedelta(days=5))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_lot_anterieur_au_plancher_stock_exclu(self):
        self._lot(100, 30, timezone.make_aware(timezone.datetime(2026, 4, 1)))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    # -- API dédiée UI (entrepôt uniquement) ---------------------------------

    def test_lots_dormants_entrepot_ignore_la_retention_superviseur_et_agent(self):
        lot_entrepot = self._lot(100, 30, timezone.now() - timedelta(days=20))
        self._affectation(100, 40, date.today() - timedelta(days=3))
        lot_agent = self._lot(100, 50, timezone.now() - timedelta(days=3))
        distribution = self._distribution(timezone.now() - timedelta(days=3))
        DetailDistribution.objects.create(distribution=distribution, lot=lot_agent, quantite=20)

        resultats = StockAgeService.lots_dormants_entrepot()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["lot"], lot_entrepot)
        self.assertEqual(resultats[0]["origine"], "entrepot")
        self.assertEqual(StockAgeService.count_lots_dormants_entrepot(), 1)

    def test_valeur_stock_dormant_entrepot_ignore_la_retention_superviseur(self):
        self._lot(100, 30, timezone.now() - timedelta(days=20))
        self._affectation(100, 40, date.today() - timedelta(days=3))

        # Seul le lot entrepôt (30 * 1000) compte, pas l'affectation superviseur (40 * 1000).
        self.assertEqual(StockAgeService.valeur_stock_dormant_entrepot(), 30 * 1000)

    # -- Stock en rétention : superviseur (3 jours) --------------------------

    def _affectation(self, quantite_initiale, quantite_restante, date_affectation, lot=None):
        return AffectationLotSuperviseur.objects.create(
            lot=lot or self._lot(100, 0, timezone.now() - timedelta(days=20)),
            superviseur=self.superviseur,
            quantite_initiale=quantite_initiale,
            quantite_restante=quantite_restante,
            date_affectation=date_affectation,
        )

    def test_lot_chez_superviseur_depuis_exactement_3_jours_present(self):
        affectation = self._affectation(100, 40, date.today() - timedelta(days=3))

        resultats = StockAgeService.lots_stock_dormant()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["origine"], "superviseur")
        self.assertEqual(resultats[0]["superviseur"], self.superviseur)
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 1)

    def test_lot_chez_superviseur_depuis_2_jours_absent(self):
        self._affectation(100, 40, date.today() - timedelta(days=2))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_lot_totalement_redistribue_par_superviseur_absent(self):
        self._affectation(100, 0, date.today() - timedelta(days=20))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    def test_affectation_anterieure_au_plancher_stock_exclue(self):
        self._affectation(100, 40, date(2026, 4, 1))

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 0)

    # -- Stock en rétention : agents de vente (3 jours, nouveau) -------------

    def test_stock_chez_agent_depuis_exactement_3_jours_present(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=3))
        distribution = self._distribution(timezone.now() - timedelta(days=3))
        DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=20)

        resultats = StockAgeService.lots_stock_dormant()

        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["origine"], "agent")
        self.assertEqual(resultats[0]["agent"], self.agent_terrain)
        self.assertEqual(resultats[0]["superviseur"], self.superviseur)
        self.assertEqual(resultats[0]["quantite_restante"], 20)
        self.assertEqual(StockAgeService.count_lots_stock_dormant(), 1)

    def test_stock_chez_agent_depuis_2_jours_absent(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=2))
        distribution = self._distribution(timezone.now() - timedelta(days=2))
        DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=20)

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])

    def test_stock_chez_agent_totalement_vendu_absent(self):
        lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
        distribution = self._distribution(timezone.now() - timedelta(days=5))
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=20)
        Vente.objects.create(
            agent=self.agent_terrain,
            detail_distribution=detail,
            quantite=20,
            prix_vente_unitaire=1200,
            date_vente=timezone.now() - timedelta(days=4),
        )

        self.assertEqual(StockAgeService.lots_stock_dormant(), [])

    def test_stock_chez_superviseur_auto_distribution_absent_du_stock_agent(self):
        # Auto-distribution (superviseur vendeur direct) : ce n'est pas un
        # "agent de vente", ne doit pas apparaître dans l'origine "agent".
        lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
        distribution = self._distribution(timezone.now() - timedelta(days=5), agent_terrain=self.superviseur)
        DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=20)

        resultats = [r for r in StockAgeService.lots_stock_dormant() if r["origine"] == "agent"]

        self.assertEqual(resultats, [])


class StockRotationViewTestCase(TestCase):
    """Régression sur l'incident observé en production (2026-08-13) :
    /surveillance/stock-rotation/ exécutait ~2400 requêtes SQL (7s de temps de
    réponse) à cause du calcul de rétention agent (N+1 sur
    quantite_restante_calculee), répété 3 fois (liste + count + valeur) et
    inutile pour cette page — la vue n'affiche que le stock entrepôt. Verrouille
    un budget de requêtes large mais très inférieur à l'incident."""

    def setUp(self):
        self.produit = Produit.objects.create(nom="Riz")
        self.direction = Agent.objects.create(
            user=User.objects.create_user(username="direction_test", password="x"),
            type_agent="direction",
        )
        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur_view"),
            type_agent="entrepot",
        )
        self.agent_terrain = Agent.objects.create(
            user=User.objects.create_user(username="agent_terrain_view"),
            type_agent="terrain",
            superviseur=self.superviseur,
        )
        self.client.force_login(self.direction.user)

    def _lot(self, quantite_initiale, quantite_restante, date_reception):
        return LotEntrepot.objects.create(
            produit=self.produit,
            quantite_initiale=quantite_initiale,
            quantite_restante=quantite_restante,
            prix_achat_unitaire=1000,
            date_reception=date_reception,
        )

    def test_page_stock_rotation_ne_calcule_pas_la_retention_agent(self):
        # Plusieurs DetailDistribution âgés, avec du stock restant chez l'agent
        # (ce qui déclenchait l'ancien N+1 s'il était encore sollicité par cette page).
        for _ in range(15):
            lot = self._lot(100, 50, timezone.now() - timedelta(days=5))
            distribution = DistributionAgent.objects.create(
                superviseur=self.superviseur,
                agent_terrain=self.agent_terrain,
                date_distribution=timezone.now() - timedelta(days=5),
            )
            DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=20)

        # Quelques lots dormants à l'entrepôt (ce que la page doit effectivement afficher).
        for _ in range(3):
            self._lot(100, 30, timezone.now() - timedelta(days=20))

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("stock_rotation"))

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(ctx.captured_queries), 40)


class DetailProduitServiceTestCase(TestCase):
    """Filtre période (semaine/mois) de detail_produit — le mois est un ajout
    du 2026-08-13, la semaine reste le comportement par défaut inchangé."""

    def setUp(self):
        self.produit = Produit.objects.create(nom="Riz")
        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur"),
            type_agent="entrepot",
        )
        self.agent = Agent.objects.create(
            user=User.objects.create_user(username="agent"),
            type_agent="terrain",
            superviseur=self.superviseur,
        )

    def _vente(self, quantite, date_vente):
        lot = LotEntrepot.objects.create(
            produit=self.produit,
            quantite_initiale=100,
            quantite_restante=100,
            prix_achat_unitaire=1000,
            date_reception=date_vente - timedelta(days=1),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.agent,
            date_distribution=date_vente - timedelta(days=1),
        )
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        return Vente.objects.create(
            agent=self.agent,
            detail_distribution=detail,
            quantite=quantite,
            prix_vente_unitaire=1200,
            date_vente=date_vente,
        )

    def test_periode_semaine_par_defaut(self):
        self._vente(10, timezone.now())

        donnees = DetailProduitService.get_data(self.produit)

        self.assertGreater(donnees["kg_actuel"], 0)

    def test_periode_mois_ignore_une_vente_hors_mois_selectionne(self):
        # Vente du mois précédent : ne doit pas compter dans le mois sélectionné.
        debut_mois_courant = timezone.make_aware(
            timezone.datetime.combine(date.today().replace(day=1), timezone.datetime.min.time())
        )
        self._vente(10, debut_mois_courant - timedelta(days=5))

        donnees = DetailProduitService.get_data(
            self.produit, debut_mois=date.today().replace(day=1), periode="mois"
        )

        self.assertEqual(donnees["kg_actuel"], 0)

    def test_periode_mois_compte_une_vente_du_mois_selectionne(self):
        debut_mois = date.today().replace(day=1)
        self._vente(10, timezone.now())

        donnees = DetailProduitService.get_data(self.produit, debut_mois=debut_mois, periode="mois")

        self.assertGreater(donnees["kg_actuel"], 0)

    def test_parse_mois_valide(self):
        self.assertEqual(parse_mois("2026-03"), date(2026, 3, 1))

    def test_parse_mois_futur_retombe_sur_mois_courant(self):
        futur = (date.today().replace(day=1) + timedelta(days=62)).replace(day=1)
        self.assertEqual(parse_mois(f"{futur.year}-{futur.month:02d}"), date.today().replace(day=1))


class DetailSuperviseurServiceTestCase(TestCase):
    """Filtre produit sur le tableau Agents de detail_superviseur — n'affecte
    que ce tableau, pas les KPI globaux du superviseur (même convention que
    ListeKgVenduService.get_agents, 2026-08-13)."""

    def setUp(self):
        self.produit_riz = Produit.objects.create(nom="Riz")
        self.produit_mil = Produit.objects.create(nom="Mil")
        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur"),
            type_agent="entrepot",
        )
        self.agent = Agent.objects.create(
            user=User.objects.create_user(username="agent"),
            type_agent="terrain",
            superviseur=self.superviseur,
        )

    def _vente(self, produit, quantite):
        lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=100,
            quantite_restante=100,
            prix_achat_unitaire=1000,
            date_reception=timezone.now() - timedelta(days=1),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.agent,
            date_distribution=timezone.now() - timedelta(days=1),
        )
        detail = DetailDistribution.objects.create(distribution=distribution, lot=lot, quantite=100)
        return Vente.objects.create(
            agent=self.agent,
            detail_distribution=detail,
            quantite=quantite,
            prix_vente_unitaire=1200,
            date_vente=timezone.now(),
        )

    def test_sans_filtre_produit_agents_stats_cumule_tout(self):
        self._vente(self.produit_riz, 10)
        self._vente(self.produit_mil, 5)

        donnees = DetailSuperviseurService.get_data(self.superviseur)

        self.assertEqual(len(donnees["agents_stats"]), 1)
        self.assertEqual(donnees["agents_stats"][0]["nb_produits"], 2)

    def test_filtre_produit_restreint_agents_stats(self):
        self._vente(self.produit_riz, 10)
        self._vente(self.produit_mil, 5)

        donnees = DetailSuperviseurService.get_data(self.superviseur, produit=self.produit_riz)

        self.assertEqual(donnees["agents_stats"][0]["nb_produits"], 1)

    def test_filtre_produit_ne_change_pas_les_kpi_globaux(self):
        self._vente(self.produit_riz, 10)
        self._vente(self.produit_mil, 5)

        sans_filtre = DetailSuperviseurService.get_data(self.superviseur)
        avec_filtre = DetailSuperviseurService.get_data(self.superviseur, produit=self.produit_riz)

        self.assertEqual(sans_filtre["kg_actuel"], avec_filtre["kg_actuel"])


class DetailProduitEtSuperviseurViewTestCase(TestCase):
    """Rendu HTTP réel des deux pages, avec les nouveaux paramètres GET
    (periode=mois / produit=<id>) — vérifie l'absence d'erreur de template."""

    def setUp(self):
        self.produit = Produit.objects.create(nom="Riz")
        self.direction = Agent.objects.create(
            user=User.objects.create_user(username="direction_test", password="x"),
            type_agent="direction",
        )
        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur_test"),
            type_agent="entrepot",
        )
        self.client.force_login(self.direction.user)

    def test_detail_produit_periode_mois(self):
        response = self.client.get(
            reverse("detail_produit", args=[self.produit.id]), {"periode": "mois"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["periode"], "mois")

    def test_detail_produit_periode_semaine_defaut(self):
        response = self.client.get(reverse("detail_produit", args=[self.produit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["periode"], "semaine")

    def test_detail_superviseur_avec_filtre_produit(self):
        response = self.client.get(
            reverse("detail_superviseur", args=[self.superviseur.id]), {"produit": self.produit.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_produit"], self.produit.id)

    def test_liste_kg_vendu_periode_semaine_defaut(self):
        response = self.client.get(reverse("liste_kg_vendu"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["periode"], "semaine")

    def test_liste_kg_vendu_periode_mois(self):
        response = self.client.get(reverse("liste_kg_vendu"), {"periode": "mois"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["periode"], "mois")
        self.assertIsNotNone(response.context["mois_selectionne"])

    def test_liste_kg_vendu_periode_mois_avec_filtre_produit(self):
        response = self.client.get(
            reverse("liste_kg_vendu"), {"periode": "mois", "produit": self.produit.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_produit"], self.produit.id)
        self.assertEqual(response.context["periode"], "mois")


class ListeKgVenduServiceTestCase(TestCase):
    """Le service (get_kpis/get_superviseurs/get_agents) reste inchangé —
    seule la vue calcule désormais les bornes de dates selon periode
    (semaine/mois) avant de les lui passer."""

    def setUp(self):
        self.produit = Produit.objects.create(nom="Riz")
        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur_kg"),
            type_agent="entrepot",
        )
        self.agent = Agent.objects.create(
            user=User.objects.create_user(username="agent_kg"),
            type_agent="terrain",
            superviseur=self.superviseur,
        )

    def test_bornes_mois_couvrent_le_mois_calendaire_entier(self):
        debut_mois = date.today().replace(day=1)
        debut, fin = ComparaisonPeriodeService.mois(debut_mois)

        self.assertEqual(debut, debut_mois)
        self.assertEqual(fin.month, debut_mois.month)
        self.assertGreaterEqual((fin - debut).days, 27)
