from decimal import Decimal
from django.db.models import Sum, F
from django.utils import timezone

from core.models import Vente, Depense, VersementBancaire, Agent
from direction.services.agent_dashboard_service import DashboardAgentAnalysisService
from direction.services.fournisseur_service import FournisseurAnalyseService
from paie.services.salaire_calculator import CalculatorSalaire


# services/analyse_financiere_service.py
from datetime import date, timedelta
from decimal import Decimal


class AnalyseFinanciereDirectionService:
    DEC_ZERO = Decimal("0.00")
    @staticmethod
    def resolve_periode(annee: int, mois: int | None):
        if mois:
            debut = date(annee, mois, 1)
            fin = (
                date(annee + 1, 1, 1)
                if mois == 12
                else date(annee, mois + 1, 1)
            ) - timedelta(days=1)
            label = f"{annee} / {mois:02d}"
            type_periode = "mensuelle"
        else:
            debut = date(annee, 1, 1)
            fin = date(annee, 12, 31)
            label = f"Année {annee}"
            type_periode = "annuelle"

        return {
            "annee": annee,
            "mois": mois,
            "debut": debut,
            "fin": fin,
            "label": label,
            "type": type_periode,
        }

    # =====================================================
    # MÉTHODE UNIQUE APPELÉE PAR LA VIEW
    # =====================================================
    @staticmethod
    def build(annee: int, mois: int | None):

        periode = AnalyseFinanciereDirectionService.resolve_periode(
            annee=annee,
            mois=mois
        )
        MOIS_FR = {
            1: "Janvier",
            2: "Février",
            3: "Mars",
            4: "Avril",
            5: "Mai",
            6: "Juin",
            7: "Juillet",
            8: "Août",
            9: "Septembre",
            10: "Octobre",
            11: "Novembre",
            12: "Décembre",
        }


        return {
            # 🔹 période officielle
            "periode": periode,

            # 🔹 filtres disponibles (pour le template)
            "filtres": {
                "annees": [2024, 2025, 2026, 2027],
                "mois": list(range(1, 13)),
            },

            # 🔹 KPI globaux
            "kpis": AnalyseFinanciereDirectionService.get_kpis_globaux(
                periode["debut"],
                periode["fin"],
            ),

            # 🔹 Agents
            "agents": {
                "superviseurs": DashboardAgentAnalysisService.get_superviseurs_finance(),
                "rot": DashboardAgentAnalysisService.get_rot_finance(),
            },

            # 🔹 Fournisseurs
            "fournisseurs": FournisseurAnalyseService.get_analyse_periode(
                periode["debut"],
                periode["fin"],
            ),
            "filtres": {
                "annees": [2024, 2025, 2026, 2027],
                "mois": [
                    {"value": k, "label": v}
                    for k, v in MOIS_FR.items()
                ],
            },

        }

    # (get_kpis_globaux identique à ce que tu as déjà)


    # =====================================================
    # KPI GLOBAUX DIRECTION
    # =====================================================
    @staticmethod
    def get_kpis_globaux(date_debut, date_fin):

        # -------------------------
        # Chiffre d’affaires
        # -------------------------
        chiffre_affaires = (
            Vente.objects.filter(
                date_vente__date__range=(date_debut, date_fin),
                est_supprime=False
            )
            .aggregate(
                total=Sum(
                    F("quantite") * F("prix_vente_unitaire")
                )
            )["total"]
            or AnalyseFinanciereDirectionService.DEC_ZERO
        )

        # -------------------------
        # Versements banque
        # -------------------------
        versements_banque = (
            VersementBancaire.objects.filter(
                date_versement_reelle__date__range=(date_debut, date_fin)
            )
            .aggregate(total=Sum("montant_vente"))["total"]
            or AnalyseFinanciereDirectionService.DEC_ZERO
        )

        # -------------------------
        # Dépenses
        # -------------------------
        depenses = (
            Depense.objects.filter(
                date_depense__date__range=(date_debut, date_fin)
            )
            .aggregate(total=Sum("montant"))["total"]
            or AnalyseFinanciereDirectionService.DEC_ZERO
        )

        # -------------------------
        # Salaires (SOURCE UNIQUE)
        # -------------------------
        salaires = AnalyseFinanciereDirectionService.get_total_salaires(
            date_debut, date_fin
        )

        # -------------------------
        # Marge
        # -------------------------
        marge = chiffre_affaires - (depenses + salaires)

        return {
            "chiffre_affaires": chiffre_affaires,
            "versements_banque": versements_banque,
            "depenses": depenses,
            "salaires": salaires,
            "marge": marge,
            "formule_marge": "Marge = CA – (Dépenses + Salaires)",
        }

    # =====================================================
    # SALAIRES – AGRÉGATION DIRECTION
    # =====================================================
    @staticmethod
    def get_total_salaires(date_debut, date_fin):

        total = AnalyseFinanciereDirectionService.DEC_ZERO

        agents = Agent.objects.filter(est_actif=True)

        for agent in agents:
            if agent.type_agent == "terrain":
                data = CalculatorSalaire.calcul_salaire_mamy(
                    agent, date_debut, date_fin
                )
            elif agent.type_agent == "agent_gros":
                data = CalculatorSalaire.calcul_salaire_gros(
                    agent, date_debut, date_fin
                )
            elif agent.type_agent in ["superviseur", "entrepot"]:
                data = CalculatorSalaire.calcul_salaire_superviseur(
                    agent, date_debut, date_fin
                )
            else:
                continue

            total += data.get(
                "salaire_total",
                AnalyseFinanciereDirectionService.DEC_ZERO
            )

        return total
