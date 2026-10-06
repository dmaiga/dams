from datetime import date, datetime, timezone as dt_tz
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Agent, Depense, Recouvrement, RecouvrementSuperviseur
from finance.services import historique_journalier, solde_superviseur


def _dt(annee, mois, jour):
    return datetime(annee, mois, jour, 10, 0, tzinfo=dt_tz.utc)


class HistoriqueJournalierTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def agent(username, type_agent, **extra):
            user = User.objects.create_user(username=username, password='x')
            return Agent.objects.create(user=user, type_agent=type_agent, **extra)

        cls.sup = agent('sup', 'entrepot')
        cls.vendeur = agent('vendeur', 'terrain', superviseur=cls.sup)
        cls.rot = agent('rot', 'rot')

        def enc(jour, montant):
            Recouvrement.objects.create(
                agent=cls.vendeur, superviseur=cls.sup, montant_recouvre=Decimal(montant),
                date_recouvrement=jour,
            )

        enc(_dt(2026, 9, 29), '1000')
        enc(_dt(2026, 9, 29), '500')
        enc(_dt(2026, 9, 30), '700')
        RecouvrementSuperviseur.objects.create(
            superviseur=cls.sup, rot=cls.rot, montant=Decimal('900'), date_recouvrement=_dt(2026, 9, 30),
        )
        Depense.objects.create(
            effectue_par=cls.sup, montant=Decimal('200'), date_depense=date(2026, 9, 29),
        )
        enc(_dt(2026, 10, 2), '300')

    def test_agrege_par_jour_et_enchaine_les_soldes(self):
        lignes = historique_journalier(self.sup, date(2026, 9, 28), date(2026, 9, 30))

        self.assertEqual([l['date'] for l in lignes], [date(2026, 9, 30), date(2026, 9, 29)])
        j29 = lignes[1]
        self.assertEqual(
            (j29['solde_debut'], j29['entrees'], j29['sorties'], j29['versements'], j29['solde_fin']),
            (Decimal('0'), Decimal('1500'), Decimal('200'), Decimal('0'), Decimal('1300')),
        )
        j30 = lignes[0]
        self.assertEqual(
            (j30['solde_debut'], j30['entrees'], j30['sorties'], j30['versements'], j30['solde_fin']),
            (Decimal('1300'), Decimal('700'), Decimal('0'), Decimal('900'), Decimal('1100')),
        )

    def test_solde_de_fin_egale_solde_superviseur(self):
        lignes = historique_journalier(self.sup, date(2026, 9, 30), date(2026, 9, 30))
        self.assertEqual(lignes[0]['solde_debut'], Decimal('1300'))
        self.assertEqual(lignes[0]['solde_fin'], solde_superviseur(self.sup, date(2026, 9, 30))['solde'])

    def test_fenetre_ulterieure_reprend_le_solde_d_ouverture(self):
        # Ne commence qu'au 30/09 : le solde de début inclut les flux du 29/09.
        lignes = historique_journalier(self.sup, date(2026, 9, 30), date(2026, 9, 30))
        self.assertEqual(lignes[0]['solde_debut'], Decimal('1300'))

    def test_bascule_du_01_10_repart_de_zero(self):
        lignes = historique_journalier(self.sup, date(2026, 9, 29), date(2026, 10, 2))
        j2 = lignes[0]
        self.assertEqual(j2['date'], date(2026, 10, 2))
        self.assertEqual((j2['solde_debut'], j2['solde_fin']), (Decimal('0'), Decimal('300')))
        self.assertEqual(j2['solde_fin'], solde_superviseur(self.sup, date(2026, 10, 2))['solde'])

    def test_aucun_mouvement(self):
        self.assertEqual(historique_journalier(self.sup, date(2026, 9, 1), date(2026, 9, 5)), [])
