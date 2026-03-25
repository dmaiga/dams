#paie/services/salaire_calculator.py
from decimal import Decimal
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from core.models import Agent, Vente, RegleSalaire
from django.utils import timezone

class CalculatorSalaire:
    """
    Moteur de calcul des salaires
    """


    @staticmethod
    def get_jours_travailles_mois(agent, date_debut, date_fin):
        """
        Retourne le nombre de jours réellement travaillés par l’agent
        dans la période (bornée au mois courant).
        """
        date_ref = agent.date_debut_fonction or agent.date_creation.date()

        debut = max(date_debut, date_ref)
        fin = min(date_fin, timezone.now().date())

        if debut > fin:
            return 0

        return (fin - debut).days + 1

    # =========================
    # UTILITAIRE
    # =========================
    @staticmethod
    def get_salaire_base(agent, type_agent):
        if agent.salaire_base_personnel is not None:
            return agent.salaire_base_personnel

        regle = RegleSalaire.objects.filter(
            type_agent=type_agent,
            actif=True
        ).first()

        return (
            getattr(regle, "salaire_base", None)
            or getattr(regle, "montant_base", None)
            or getattr(regle, "salaire_fixe", None)
            or Decimal("0.00")
        )

    # =========================
    # AGENT TERRAIN (MAMY)
    # =========================
    @staticmethod
    def calcul_salaire_mamy(agent, date_debut, date_fin):
    
        # Salaire de base théorique (ex: 20 000)
        salaire_base_theorique = CalculatorSalaire.get_salaire_base(agent, "terrain")
    
        # Nombre de jours dans le mois
        total_jours_mois = (date_fin - date_debut).days + 1
    
        # Jours réellement travaillés
        jours_travailles = CalculatorSalaire.get_jours_travailles_mois(
            agent, date_debut, date_fin
        )
    
        # 🔹 PRORATISATION SI < 1 MOIS
        if agent.date_debut_fonction and jours_travailles < total_jours_mois:
            salaire_base = (
                salaire_base_theorique
                * Decimal(jours_travailles)
                / Decimal(total_jours_mois)
            ).quantize(Decimal("1"))
        else:
            salaire_base = salaire_base_theorique
    
        # ===== INCENTIVE (INCHANGÉ) =====
        regle = RegleSalaire.objects.filter(
            type_agent="terrain",
            actif=True
        ).first()
    
        incentive_par_kg = getattr(regle, "incentive_par_kg", Decimal("0.00"))
    
        ventes = Vente.objects.filter(
            agent=agent,
            date_vente__date__range=(date_debut, date_fin),
            est_supprime=False,
        )
    
        kilo_total = ventes.aggregate(
            total=Coalesce(
                Sum(
                    F("quantite") *
                    Coalesce(
                        F("detail_distribution__lot__produit__poids_unitaire_kg"),
                        Decimal("1")
                    )
                ),
                Decimal("0.00")
            )
        )["total"]
    
        incentive = kilo_total * incentive_par_kg
    
        return {
            "salaire_base": salaire_base,
            "salaire_base_theorique": salaire_base_theorique,
            "jours_travailles": jours_travailles,
            "jours_mois": total_jours_mois,
            "incentive": incentive,
            "bonus": Decimal("0.00"),
            "salaire_total": salaire_base + incentive,
            "kilo_total": kilo_total,
        }
    
    # =========================
    # AGENT GROS
    # =========================
    @staticmethod
    def calcul_salaire_gros(agent, date_debut, date_fin):

        regle = RegleSalaire.objects.filter(
            type_agent="agent_gros",
            actif=True
        ).first()

        incentive_par_carton = getattr(regle, "incentive_par_carton", Decimal("0.00"))

        ventes = Vente.objects.filter(
            agent=agent,
            date_vente__date__range=(date_debut, date_fin),
            est_supprime=False,
        )

        cartons = ventes.aggregate(
            total=Coalesce(Sum("quantite"), Decimal("0.00"))
        )["total"]

        if cartons < 150:
            salaire = cartons * incentive_par_carton
        elif cartons < 200:
            salaire = Decimal("50000")
        else:
            salaire = Decimal("90000")

        return {
            "salaire_base": Decimal("0.00"),
            "incentive": salaire,
            "bonus": Decimal("0.00"),
            "salaire_total": salaire,
            "cartons_total": cartons,
        }

    # =========================
    # SUPERVISEUR
    # =========================
    @staticmethod
    def calcul_salaire_superviseur(superviseur, date_debut, date_fin):

        salaire_base = CalculatorSalaire.get_salaire_base(superviseur, "superviseur")

        regle = RegleSalaire.objects.filter(
            type_agent="superviseur",
            actif=True
        ).first()

        dotation = getattr(regle, "dotation_fonction", Decimal("0.00"))

        agents = Agent.objects.filter(
            superviseur=superviseur,
            type_agent="terrain",
            est_actif=True
        )

        kilo_total_mamies = Decimal("0.00")

        for agent in agents:
            data = CalculatorSalaire.calcul_salaire_mamy(agent, date_debut, date_fin)
            kilo_total_mamies += data["kilo_total"]

        if kilo_total_mamies < Decimal("18000"):
            taux = Decimal("0")
        elif kilo_total_mamies < Decimal("27000"):
            taux = Decimal("0.04")
        elif kilo_total_mamies < Decimal("37000"):
            taux = Decimal("0.06")
        else:
            taux = Decimal("0.08")

        bonus = kilo_total_mamies * taux

        return {
            "salaire_base": salaire_base,
            "dotation": dotation,
            "bonus": bonus,
            "taux_bonus": taux,
            "kilo_total_mamies": kilo_total_mamies,
            "salaire_total": salaire_base + dotation + bonus,
        }
