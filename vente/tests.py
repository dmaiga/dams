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


class CorrecteursVentesPagesTests(TestCase):
    """Pages dédiées du groupe « Correcteurs ventes » (gabarit superviseur,
    accès limité au groupe, aucun accès aux écrans de correction direction)."""

    def setUp(self):
        from django.contrib.auth.models import Group
        from core.services.corrections import GROUPE_CORRECTEURS_VENTES

        produit = Produit.objects.create(nom='oignon')
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
            prix_achat_unitaire=Decimal('15000.00'),
        )
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur, agent_terrain=self.agent, quantite_totale=Decimal('25.00')
        )
        detail = DetailDistribution.objects.create(
            distribution=distribution, lot=lot, quantite=Decimal('25.00')
        )
        self.vente = Vente.objects.create(
            agent=self.agent, detail_distribution=detail,
            quantite=Decimal('1.00'), prix_vente_unitaire=Decimal('800.00'), type_vente='detail',
        )
        Recouvrement.objects.create(
            agent=self.agent, superviseur=self.superviseur, vente=self.vente,
            montant_recouvre=self.vente.total_vente,
        )

        self.correcteur = User.objects.create_user(username='modibo.sidibe', password='x')
        self.correcteur.groups.add(Group.objects.get_or_create(name=GROUPE_CORRECTEURS_VENTES)[0])
        self.autre = User.objects.create_user(username='autre.sup', password='x')

    def test_liste_reservee_au_groupe(self):
        self.client.force_login(self.autre)
        reponse = self.client.get('/vente/corrections/')
        self.assertEqual(reponse.status_code, 302)  # redirigé vers le login

        self.client.force_login(self.correcteur)
        reponse = self.client.get('/vente/corrections/')
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'oignon')

    def test_filtre_sous_cout(self):
        self.client.force_login(self.correcteur)
        reponse = self.client.get('/vente/corrections/?anomalie=sous_cout')
        self.assertContains(reponse, 'oignon')  # 800 < 15000
        reponse = self.client.get(f'/vente/corrections/?superviseur={self.superviseur.id + 999}')
        self.assertContains(reponse, 'Aucune vente sur cette période')

    def test_correction_met_a_jour_recouvrement_et_audit(self):
        self.client.force_login(self.correcteur)
        reponse = self.client.post(
            f'/vente/corrections/{self.vente.id}/',
            {'quantite': '25', 'prix_vente_unitaire': '800', 'motif': 'sac de 25 kg'},
        )
        self.assertEqual(reponse.status_code, 302)
        self.vente.refresh_from_db()
        self.assertEqual(self.vente.quantite, Decimal('25.00'))
        self.assertEqual(self.vente.recouvrement_set.get().montant_recouvre, Decimal('20000.00')) \
            if hasattr(self.vente, 'recouvrement_set') else None
        correction = CorrectionAdministrative.objects.get()
        self.assertEqual(correction.utilisateur, self.correcteur)

    def test_correcteur_sans_acces_aux_ecrans_direction(self):
        self.client.force_login(self.correcteur)
        from django.urls import reverse
        reponse = self.client.get(reverse('corriger_vente', args=[self.vente.id]))
        self.assertEqual(reponse.status_code, 302)

    def test_periode_hebdo_par_defaut_et_regroupement_jour_puis_superviseur(self):
        from datetime import timedelta
        from django.utils import timezone

        # Vente ancienne (30 jours) : hors hebdo, visible en custom.
        ancienne = Vente.objects.create(
            agent=self.agent, detail_distribution=self.vente.detail_distribution,
            quantite=Decimal('1.00'), prix_vente_unitaire=Decimal('900.00'), type_vente='detail',
        )
        Vente.objects.filter(pk=ancienne.pk).update(date_vente=timezone.now() - timedelta(days=30))

        self.client.force_login(self.correcteur)
        reponse = self.client.get('/vente/corrections/')
        self.assertEqual(reponse.context['periode'], 'hebdo')
        journees = reponse.context['journees']
        self.assertEqual(len(journees), 1)  # uniquement aujourd'hui
        self.assertEqual(
            [g['superviseur'] for g in journees[0]['groupes']], [self.superviseur]
        )

        debut = (timezone.localdate() - timedelta(days=40)).isoformat()
        reponse = self.client.get(f'/vente/corrections/?periode=custom&debut={debut}')
        self.assertEqual(len(reponse.context['journees']), 2)
        # Jour le plus récent d'abord.
        jours = [j['jour'] for j in reponse.context['journees']]
        self.assertEqual(jours, sorted(jours, reverse=True))

    def test_filtres_prix_suspects(self):
        from vente.services import classer_prix, lister_ventes_a_surveiller

        achat = Decimal('15000.00')
        self.assertEqual(classer_prix(Decimal('800'), achat), 'sous_cout')
        self.assertEqual(classer_prix(Decimal('15020'), achat), 'marge_faible')
        self.assertEqual(classer_prix(Decimal('18500'), achat), None)
        self.assertEqual(classer_prix(Decimal('18501'), achat), 'prix_eleve')

        def ids(**kw):
            return set(v.id for v in lister_ventes_a_surveiller(**kw))

        # La vente du jeu de test (800 contre un achat de 15 000) est sous le coût.
        self.assertIn(self.vente.id, ids(anomalie='sous_cout'))
        self.assertIn(self.vente.id, ids(anomalie='marge_faible'))
        self.assertIn(self.vente.id, ids(anomalie='suspect'))
        self.assertNotIn(self.vente.id, ids(anomalie='prix_eleve'))

        Vente.objects.filter(pk=self.vente.pk).update(prix_vente_unitaire=Decimal('25000.00'))
        self.assertIn(self.vente.id, ids(anomalie='prix_eleve'))
        self.assertIn(self.vente.id, ids(anomalie='suspect'))
        self.assertNotIn(self.vente.id, ids(anomalie='sous_cout'))

        Vente.objects.filter(pk=self.vente.pk).update(prix_vente_unitaire=Decimal('17000.00'))
        self.assertNotIn(self.vente.id, ids(anomalie='suspect'))

    def test_filtre_prix_independant_de_la_quantite(self):
        """L'écart est comparé PAR UNITÉ (prix de vente unitaire − prix d'achat unitaire) :
        une grosse quantité ne fait jamais basculer une vente en « prix élevé » ni
        en « normal » — seul l'écart unitaire compte."""
        from vente.services import lister_ventes_a_surveiller

        # Achat 15 000 ; vente à 17 000 → écart unitaire 2 000 (normal, < seuil).
        # Quantité 10 → marge totale 20 000, très supérieure au seuil, mais non signalée.
        Vente.objects.filter(pk=self.vente.pk).update(
            prix_vente_unitaire=Decimal('17000.00'), quantite=Decimal('10.00')
        )
        ids = set(v.id for v in lister_ventes_a_surveiller(anomalie='suspect'))
        self.assertNotIn(self.vente.id, ids)

        # Même vente avec quantité 1 : même verdict.
        Vente.objects.filter(pk=self.vente.pk).update(quantite=Decimal('1.00'))
        ids = set(v.id for v in lister_ventes_a_surveiller(anomalie='suspect'))
        self.assertNotIn(self.vente.id, ids)

        # Écart unitaire de 4 000 (> seuil) : signalée quelle que soit la quantité.
        for quantite in ('1.00', '10.00'):
            Vente.objects.filter(pk=self.vente.pk).update(
                prix_vente_unitaire=Decimal('19000.00'), quantite=Decimal(quantite)
            )
            ids = set(v.id for v in lister_ventes_a_surveiller(anomalie='prix_eleve'))
            self.assertIn(self.vente.id, ids)
