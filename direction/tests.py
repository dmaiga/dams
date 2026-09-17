from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        self.superviseur = Agent.objects.create(user=sup_user, type_agent='entrepot')
        agent_user = User.objects.create_user(username='agent1', password='x')
        self.agent = Agent.objects.create(user=agent_user, type_agent='terrain', superviseur=self.superviseur)

        self.lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=Decimal('100.00'),
            quantite_restante=Decimal('100.00'),
            prix_achat_unitaire=Decimal('250.00'),
        )
        self.distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur, agent_terrain=self.agent, quantite_totale=Decimal('20.00')
        )
        self.detail = DetailDistribution.objects.create(
            distribution=self.distribution, lot=self.lot, quantite=Decimal('20.00')
        )
        self.vente = Vente.objects.create(
            agent=self.agent,
            detail_distribution=self.detail,
            quantite=Decimal('1.00'),
            prix_vente_unitaire=Decimal('800.00'),
            type_vente='detail',
        )

    def _urls(self):
        return [
            reverse('liste_corrections_lots'),
            reverse('liste_corrections_distributions'),
            reverse('liste_corrections_ventes'),
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

    def test_mdmaiga_accede_aux_7_ecrans(self):
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

    def test_correction_lot_sans_motif_est_acceptee(self):
        # Décision mdmaiga (2026-09-15) : le motif est facultatif.
        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('corriger_lot', args=[self.lot.id]),
            {
                'quantite_initiale': '120.00',
                'prix_achat_unitaire': '',
                'fournisseur': '',
                'date_reception': '',
                'motif': '',
            },
        )
        self.assertRedirects(response, reverse('historique_corrections'))
        self.assertEqual(CorrectionAdministrative.objects.count(), 1)
        self.assertEqual(CorrectionAdministrative.objects.get().motif, '')

    def test_correction_lot_sans_aucun_champ_est_rejetee_par_le_formulaire(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('corriger_lot', args=[self.lot.id]),
            {
                'quantite_initiale': '',
                'prix_achat_unitaire': '',
                'fournisseur': '',
                'date_reception': '',
                'motif': 'Un motif mais aucun champ à corriger',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CorrectionAdministrative.objects.count(), 0)
        self.assertFalse(response.context['form'].is_valid())

    def test_correction_distribution_via_formulaire_repercute_sur_le_stock(self):
        # Bout en bout : "j'ai distribué 20, je corrige à 18" — le stock
        # central doit recevoir la différence (2 restitués).
        from core.models import AffectationLotSuperviseur
        from datetime import date

        # Les 20 déjà distribués sont déjà sortis du stock central.
        self.lot.quantite_restante = Decimal('80.00')
        self.lot.save()

        AffectationLotSuperviseur.objects.create(
            lot=self.lot,
            superviseur=self.superviseur,
            quantite_initiale=Decimal('20.00'),
            quantite_restante=Decimal('0.00'),
            agent_terrain_direct=self.agent,
            date_affectation=date.today(),
        )

        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('corriger_distribution', args=[self.detail.id]),
            {
                'superviseur': self.superviseur.id,
                'agent_terrain': self.agent.id,
                'produit': '',
                'lot': '',
                'quantite': '18.00',
                'date_distribution': '',
                'motif': '',
            },
        )
        self.assertRedirects(response, reverse('historique_corrections'))
        self.detail.refresh_from_db()
        self.lot.refresh_from_db()
        self.assertEqual(self.detail.quantite, Decimal('18.00'))
        self.assertEqual(self.lot.quantite_restante, Decimal('82.00'))
        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'DISTRIBUTION_QUANTITE')

    def test_suppression_distribution_via_formulaire_restitue_le_stock(self):
        from core.models import AffectationLotSuperviseur
        from datetime import date

        # Distribution en double : aucune vente dessus, cible du doublon.
        doublon = DistributionAgent.objects.create(
            superviseur=self.superviseur, agent_terrain=self.agent, quantite_totale=Decimal('10.00')
        )
        detail_doublon = DetailDistribution.objects.create(
            distribution=doublon, lot=self.lot, quantite=Decimal('10.00')
        )
        self.lot.quantite_restante = Decimal('90.00')
        self.lot.save()
        AffectationLotSuperviseur.objects.create(
            lot=self.lot,
            superviseur=self.superviseur,
            quantite_initiale=Decimal('10.00'),
            quantite_restante=Decimal('0.00'),
            agent_terrain_direct=self.agent,
            date_affectation=date.today(),
        )

        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('supprimer_distribution_admin', args=[detail_doublon.id]),
            {'motif': 'Doublon'},
        )
        self.assertRedirects(response, reverse('historique_corrections'))
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, Decimal('100.00'))
        self.assertFalse(DetailDistribution.objects.filter(pk=detail_doublon.pk).exists())
        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.type_correction, 'DISTRIBUTION_SUPPRESSION')

    def test_suppression_distribution_refusee_redirige_avec_message(self):
        # self.detail porte déjà self.vente (créée dans setUp) — refusée.
        self.client.login(username='mdmaiga', password='x')
        response = self.client.post(
            reverse('supprimer_distribution_admin', args=[self.detail.id]),
            {'motif': ''},
        )
        self.assertRedirects(response, reverse('corriger_distribution', args=[self.detail.id]))
        self.assertTrue(DetailDistribution.objects.filter(pk=self.detail.pk).exists())

    def test_liste_lots_filtre_par_produit_et_periode(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.get(reverse('liste_corrections_lots'), {'produit': self.lot.produit_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.lot, response.context['page_obj'])

        response = self.client.get(reverse('liste_corrections_lots'), {'debut': '2099-01-01'})
        self.assertNotIn(self.lot, response.context['page_obj'])

    def test_liste_distributions_filtre_par_agent(self):
        self.client.login(username='mdmaiga', password='x')
        agent = self.detail.distribution.agent_terrain
        response = self.client.get(reverse('liste_corrections_distributions'), {'agent': agent.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.detail, response.context['page_obj'])

    def test_liste_ventes_filtre_par_agent(self):
        self.client.login(username='mdmaiga', password='x')
        response = self.client.get(reverse('liste_corrections_ventes'), {'agent': self.vente.agent_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.vente, response.context['page_obj'])


class SuiviDistributionsProduitsEnCirculationTests(TestCase):
    """sprint-14 (17/09/2026) — filtre par défaut, valorisation sans prix de
    vente, seuils de couleur réels (7 j / 14 j) et 2e tableau d'investigation."""

    def setUp(self):
        produit = Produit.objects.create(nom='oignon')

        user = User.objects.create_user(username='direction1', password='x')
        Agent.objects.create(user=user, type_agent='direction')

        sup_user = User.objects.create_user(username='sup1', password='x')
        self.superviseur = Agent.objects.create(user=sup_user, type_agent='entrepot')
        agent_user = User.objects.create_user(username='agent1', password='x')
        self.agent = Agent.objects.create(user=agent_user, type_agent='terrain', superviseur=self.superviseur)

        self.lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=Decimal('300.00'),
            quantite_restante=Decimal('300.00'),
            prix_achat_unitaire=Decimal('250.00'),
        )

        def _detail_sorti_il_y_a(jours, quantite=Decimal('10.00')):
            distribution = DistributionAgent.objects.create(
                superviseur=self.superviseur,
                agent_terrain=self.agent,
                quantite_totale=quantite,
                date_distribution=timezone.now() - timezone.timedelta(days=jours),
            )
            return DetailDistribution.objects.create(
                distribution=distribution, lot=self.lot, quantite=quantite
            )

        self.detail_recent = _detail_sorti_il_y_a(2)       # < 7 j : neutre
        self.detail_attention = _detail_sorti_il_y_a(10)   # 7-13 j : attention
        self.detail_critique = _detail_sorti_il_y_a(20)    # >= 14 j : critique

        # Écoulé : ne doit jamais apparaître dans "en circulation" ni dans le
        # tableau d'investigation, même s'il est vieux de 30 jours.
        self.detail_ecoule = _detail_sorti_il_y_a(30, quantite=Decimal('5.00'))
        Vente.objects.create(
            agent=self.agent,
            detail_distribution=self.detail_ecoule,
            quantite=Decimal('5.00'),
            prix_vente_unitaire=Decimal('800.00'),
            type_vente='detail',
        )

        self.client.login(username='direction1', password='x')

    def test_filtre_par_defaut_ne_montre_que_les_produits_en_circulation(self):
        response = self.client.get(reverse('suivi_distributions'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['statut_filtre'], 'restant')
        details_affiches = list(response.context['page_obj'])
        self.assertNotIn(self.detail_ecoule, details_affiches)
        self.assertIn(self.detail_recent, details_affiches)

    def test_statut_tous_inclut_les_produits_ecoules(self):
        response = self.client.get(reverse('suivi_distributions'), {'statut': 'tous'})
        self.assertEqual(response.context['statut_filtre'], 'tous')
        self.assertIn(self.detail_ecoule, list(response.context['page_obj']))

    def test_valorisation_ne_contient_jamais_le_prix_de_vente(self):
        # Bug corrigé (sprint-14) : d.prix_detail est toujours None avant
        # vente (rules/ARCHITECTURE.md), donc plus jamais affiché.
        response = self.client.get(reverse('suivi_distributions'), {'statut': 'tous'})
        self.assertNotContains(response, 'None FCFA')
        self.assertNotContains(response, 'PRIX VENTE VARIABLE')

    def test_seuils_de_couleur_sur_la_circulation(self):
        response = self.client.get(reverse('suivi_distributions'))
        details_par_id = {d.id: d for d in response.context['page_obj']}

        self.assertEqual(details_par_id[self.detail_recent.id].statut_circulation, 'ok')
        self.assertEqual(details_par_id[self.detail_attention.id].statut_circulation, 'attention')
        self.assertEqual(details_par_id[self.detail_critique.id].statut_circulation, 'critique')

    def test_valeur_immobilisee_correspond_au_prix_achat(self):
        response = self.client.get(reverse('suivi_distributions'))
        details_par_id = {d.id: d for d in response.context['page_obj']}
        # 10 unités x 250 FCFA (prix d'achat du lot) restantes sur le détail récent.
        self.assertEqual(
            details_par_id[self.detail_recent.id].valeur_immobilisee,
            Decimal('2500.00'),
        )

    def test_tableau_a_investiguer_regroupe_par_superviseur_puis_agent(self):
        # sprint-14, révision 17/09/2026 : checklist terrain regroupée
        # superviseur -> agent -> produits, sans fournisseur ni valorisation.
        response = self.client.get(reverse('suivi_distributions'))
        groupes = response.context['agents_a_investiguer']

        self.assertEqual(len(groupes), 1)
        groupe = groupes[0]
        self.assertEqual(groupe['superviseur'], self.superviseur)
        self.assertEqual(groupe['nb_agents'], 1)

        bloc_agent = groupe['agents'][0]
        self.assertEqual(bloc_agent['agent'], self.agent)
        noms_produits = {p['produit_nom'] for p in bloc_agent['produits']}
        self.assertEqual(noms_produits, {'oignon'})
        self.assertEqual(bloc_agent['nb_produits'], 2)  # attention + critique, pas le récent ni l'écoulé

        jours_par_produit = sorted(p['jours_ecoules'] for p in bloc_agent['produits'])
        self.assertEqual(jours_par_produit, [10, 20])

    def test_tableau_a_investiguer_exclut_les_superviseurs_inactifs(self):
        self.superviseur.est_actif = False
        self.superviseur.save()

        response = self.client.get(reverse('suivi_distributions'))
        self.assertEqual(response.context['agents_a_investiguer'], [])
        self.assertEqual(response.context['nb_agents_a_investiguer'], 0)

        # Le filtre du formulaire ne propose déjà que les superviseurs actifs.
        self.assertNotIn(self.superviseur, list(response.context['superviseurs']))

    def test_export_excel_et_pdf_produits_a_investiguer(self):
        response_excel = self.client.get(reverse('export_produits_investigation_excel'))
        self.assertEqual(response_excel.status_code, 200)
        self.assertEqual(
            response_excel['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response_pdf = self.client.get(reverse('export_produits_investigation_pdf'))
        self.assertEqual(response_pdf.status_code, 200)
        self.assertEqual(response_pdf['Content-Type'], 'application/pdf')


class VentesSuperviseurAffichageTests(TestCase):
    """sprint-14 (17/09/2026) — le superviseur de l'agent doit être visible
    sur direction/ventes sans requête N+1 supplémentaire."""

    def setUp(self):
        produit = Produit.objects.create(nom='tomate')

        user = User.objects.create_user(username='direction2', password='x')
        Agent.objects.create(user=user, type_agent='direction')

        sup_user = User.objects.create_user(username='sup2', password='x')
        self.superviseur = Agent.objects.create(user=sup_user, type_agent='entrepot')
        agent_user = User.objects.create_user(username='agent2', password='x')
        self.agent = Agent.objects.create(user=agent_user, type_agent='terrain', superviseur=self.superviseur)

        lot = LotEntrepot.objects.create(
            produit=produit,
            quantite_initiale=Decimal('50.00'),
            quantite_restante=Decimal('50.00'),
            prix_achat_unitaire=Decimal('250.00'),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur, agent_terrain=self.agent, quantite_totale=Decimal('10.00')
        )
        detail = DetailDistribution.objects.create(
            distribution=distribution, lot=lot, quantite=Decimal('10.00')
        )
        self.vente = Vente.objects.create(
            agent=self.agent,
            detail_distribution=detail,
            quantite=Decimal('2.00'),
            prix_vente_unitaire=Decimal('800.00'),
            type_vente='detail',
        )

        self.client.login(username='direction2', password='x')

    def test_nom_du_superviseur_visible_sous_le_nom_de_l_agent(self):
        response = self.client.get(reverse('toutes_les_ventes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.superviseur.full_name)
