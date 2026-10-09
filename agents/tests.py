from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agents.services.stock_agents_service import StockAgentsService
from core.models import (
    Agent, DetailDistribution, DistributionAgent, LotEntrepot, Produit,
)
from direction.constants import DATE_DEBUT_SUIVI_TERRAIN


class StockAgentsTests(TestCase):
    """Produits en possession des agents d'un superviseur : récents (< 7 j)
    et anciens (≥ 7 j), séparés."""

    def setUp(self):
        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username='sup1', password='x'), type_agent='entrepot'
        )
        self.agent = Agent.objects.create(
            user=User.objects.create_user(username='agent1', password='x'),
            type_agent='terrain', superviseur=self.superviseur,
        )
        autre_sup = Agent.objects.create(
            user=User.objects.create_user(username='sup2', password='x'), type_agent='entrepot'
        )
        self.agent_autre = Agent.objects.create(
            user=User.objects.create_user(username='agent2', password='x'),
            type_agent='terrain', superviseur=autre_sup,
        )
        self.now = timezone.now()

    def _distribuer(self, agent, nom_produit, jours, quantite='10.00'):
        produit = Produit.objects.create(nom=nom_produit)
        lot = LotEntrepot.objects.create(
            produit=produit, quantite_initiale=Decimal('100.00'),
            quantite_restante=Decimal('100.00'), prix_achat_unitaire=Decimal('100.00'),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=agent.superviseur, agent_terrain=agent,
            quantite_totale=Decimal(quantite),
        )
        # date_distribution est auto (auto_now_add) : on la fixe par update.
        DistributionAgent.objects.filter(pk=distribution.pk).update(
            date_distribution=self.now - timedelta(days=jours)
        )
        return DetailDistribution.objects.create(
            distribution=distribution, lot=lot, quantite=Decimal(quantite)
        )

    def test_separe_recents_et_anciens(self):
        # Si la date de départ du suivi est dans le futur d'un jeu de test, rien à vérifier.
        self.assertLess(DATE_DEBUT_SUIVI_TERRAIN, self.now.date())
        self._distribuer(self.agent, 'oignon', jours=2)
        self._distribuer(self.agent, 'tomate', jours=9)
        self._distribuer(self.agent_autre, 'ail', jours=20)  # autre superviseur : exclu

        blocs = StockAgentsService.produits_par_agent(superviseur=self.superviseur)

        self.assertEqual(len(blocs), 1)
        bloc = blocs[0]
        self.assertEqual([p['produit_nom'] for p in bloc['recents']], ['oignon'])
        self.assertEqual([p['produit_nom'] for p in bloc['anciens']], ['tomate'])
        self.assertEqual(bloc['anciens'][0]['statut'], 'attention')

    def test_produit_vendu_en_totalite_nest_plus_en_possession(self):
        from core.models import Vente
        detail = self._distribuer(self.agent, 'oignon', jours=10)
        Vente.objects.create(
            agent=self.agent, detail_distribution=detail,
            quantite=Decimal('10.00'), prix_vente_unitaire=Decimal('150.00'),
        )
        self.assertEqual(StockAgentsService.produits_par_agent(superviseur=self.superviseur), [])

    def test_fiche_agent_du_superviseur_liste_les_produits(self):
        self._distribuer(self.agent, 'tomate', jours=9)
        self.client.force_login(self.superviseur.user)
        reponse = self.client.get(f'/agents/sup/agent/{self.agent.id}/')
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Produits en sa possession')
        self.assertContains(reponse, 'tomate')

    def test_suivi_stock_gestionnaire_voit_tous_les_agents(self):
        self._distribuer(self.agent, 'tomate', jours=9)
        self._distribuer(self.agent_autre, 'ail', jours=3)
        gestionnaire = Agent.objects.create(
            user=User.objects.create_user(username='gest', password='x'),
            type_agent='gestionnaire_stock',
        )
        self.client.force_login(gestionnaire.user)
        reponse = self.client.get(reverse('suivi_stock_agents'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Produits à investiguer')
        self.assertContains(reponse, 'tomate')
        self.assertContains(reponse, 'ail')

    def test_suivi_stock_groupe_ok_superviseur_ordinaire_refuse(self):
        from django.contrib.auth.models import Group
        from core.services.acces import GROUPE_SUIVI_STOCK_AGENTS

        self.client.force_login(self.superviseur.user)
        self.assertEqual(self.client.get(reverse('suivi_stock_agents')).status_code, 302)

        self.superviseur.user.groups.add(
            Group.objects.get_or_create(name=GROUPE_SUIVI_STOCK_AGENTS)[0]
        )
        self.assertEqual(self.client.get(reverse('suivi_stock_agents')).status_code, 200)
