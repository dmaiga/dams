from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Agent,
    DetailDistribution,
    DistributionAgent,
    LotEntrepot,
    Perte,
    Produit,
    RegleSalaire,
    Vente,
)
from paie.services.salaire_calculator import CalculatorSalaire


class CalculSalaireMamyPertesTestCase(TestCase):
    """Sprint-10 : les kilos perdus déclarés par le superviseur (Perte.kilo_perdu_incentive)
    doivent réduire l'incentive de l'agent (25 FCFA/kg) et le seuil des 750 kg du fixe,
    aussi bien pour un produit vrac que pour un produit conditionné (sac/carton)."""

    def setUp(self):
        RegleSalaire.objects.create(type_agent="terrain", incentive_par_kg=Decimal("25"))

        self.superviseur = Agent.objects.create(
            user=User.objects.create_user(username="superviseur"),
            type_agent="entrepot",
        )
        self.agent = Agent.objects.create(
            user=User.objects.create_user(username="agent"),
            type_agent="terrain",
            superviseur=self.superviseur,
        )
        self.distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=self.agent,
            date_distribution=timezone.now(),
        )
        self.date_debut = date(2026, 8, 1)
        self.date_fin = date(2026, 8, 31)

    def _vente(self, detail, quantite, date_vente=None):
        return Vente.objects.create(
            agent=self.agent,
            detail_distribution=detail,
            quantite=quantite,
            prix_vente_unitaire=1000,
            date_vente=date_vente or timezone.make_aware(
                timezone.datetime.combine(self.date_debut, timezone.datetime.min.time())
            ),
        )

    def test_vente_vrac_sans_perte_incentive_sur_kilo_brut(self):
        produit = Produit.objects.create(nom="Riz")  # vrac : poids_unitaire_kg vide
        lot = LotEntrepot.objects.create(produit=produit, quantite_initiale=100, quantite_restante=100, prix_achat_unitaire=500)
        detail = DetailDistribution.objects.create(distribution=self.distribution, lot=lot, quantite=100)
        self._vente(detail, quantite=20)

        resultat = CalculatorSalaire.calcul_salaire_mamy(self.agent, self.date_debut, self.date_fin)

        self.assertEqual(resultat["kilo_total"], Decimal("20"))
        self.assertEqual(resultat["kilo_perdu"], Decimal("0.00"))
        self.assertEqual(resultat["kilo_facturable"], Decimal("20"))
        self.assertEqual(resultat["incentive"], Decimal("500"))  # 20 * 25

    def test_vente_vrac_avec_perte_partielle_reduit_incentive(self):
        produit = Produit.objects.create(nom="Riz")
        lot = LotEntrepot.objects.create(produit=produit, quantite_initiale=100, quantite_restante=100, prix_achat_unitaire=500)
        detail = DetailDistribution.objects.create(distribution=self.distribution, lot=lot, quantite=100)
        vente = self._vente(detail, quantite=20)
        Perte.objects.create(
            detail_distribution=detail,
            vente=vente,
            quantite_perdue=Decimal("5"),
            kilo_perdu_incentive=Decimal("5"),
            description="Perdu (déclaré à la vente)",
        )

        resultat = CalculatorSalaire.calcul_salaire_mamy(self.agent, self.date_debut, self.date_fin)

        self.assertEqual(resultat["kilo_total"], Decimal("20"))
        self.assertEqual(resultat["kilo_perdu"], Decimal("5"))
        self.assertEqual(resultat["kilo_facturable"], Decimal("15"))
        self.assertEqual(resultat["incentive"], Decimal("375"))  # (20 - 5) * 25

    def test_vente_conditionnee_avec_perte_partielle_en_kg_ne_touche_pas_le_stock(self):
        # Sac de 25 kg : l'agent vend 1 sac, mais 5 kg sont déclarés perdus à
        # l'intérieur du sac — le sac reste compté comme vendu (quantite_perdue=0),
        # seul kilo_perdu_incentive réduit l'incentive.
        produit = Produit.objects.create(nom="Oignon (sac)", poids_unitaire_kg=Decimal("25"))
        lot = LotEntrepot.objects.create(produit=produit, quantite_initiale=10, quantite_restante=10, prix_achat_unitaire=500)
        detail = DetailDistribution.objects.create(distribution=self.distribution, lot=lot, quantite=10)
        vente = self._vente(detail, quantite=1)
        Perte.objects.create(
            detail_distribution=detail,
            vente=vente,
            quantite_perdue=Decimal("0.00"),
            kilo_perdu_incentive=Decimal("5"),
            description="5 kg abîmés dans le sac",
        )

        resultat = CalculatorSalaire.calcul_salaire_mamy(self.agent, self.date_debut, self.date_fin)

        # kilo_total = 1 sac * 25 kg/sac = 25 kg brut ; net = 25 - 5 = 20 kg.
        self.assertEqual(resultat["kilo_total"], Decimal("25"))
        self.assertEqual(resultat["kilo_perdu"], Decimal("5"))
        self.assertEqual(resultat["kilo_facturable"], Decimal("20"))
        self.assertEqual(resultat["incentive"], Decimal("500"))  # (25 - 5) * 25

        # Le décompte de stock (en sacs) n'est pas affecté par kilo_perdu_incentive :
        # 10 sacs distribués - 1 sac vendu - 0 (quantite_perdue) = 9 restants.
        detail.refresh_from_db()
        self.assertEqual(detail.quantite_restante_calculee, Decimal("9"))

    def test_seuil_750kg_calcule_sur_le_kilo_facturable_net(self):
        produit = Produit.objects.create(nom="Riz")
        lot = LotEntrepot.objects.create(produit=produit, quantite_initiale=1000, quantite_restante=1000, prix_achat_unitaire=500)
        detail = DetailDistribution.objects.create(distribution=self.distribution, lot=lot, quantite=1000)
        vente = self._vente(detail, quantite=760)  # brut >= 750, net < 750 après perte
        Perte.objects.create(
            detail_distribution=detail,
            vente=vente,
            quantite_perdue=Decimal("15"),
            kilo_perdu_incentive=Decimal("15"),
            description="Perdu (déclaré à la vente)",
        )

        resultat = CalculatorSalaire.calcul_salaire_mamy(self.agent, self.date_debut, self.date_fin)

        self.assertEqual(resultat["kilo_facturable"], Decimal("745"))
        self.assertEqual(resultat["salaire_base_theorique"], Decimal("10000"))
