from decimal import Decimal
from core.models import Agent
from paie.services.salaire_calculator import CalculatorSalaire


class SalaireListeService:
    """
    Service Direction – Liste des salaires à verser (LECTURE SEULE)
    """

    @staticmethod
    def get_salaires(date_debut, date_fin, type_agent_filter=""):

        agents = Agent.objects.filter(
            est_actif=True,
            type_agent__in=["terrain", "agent_gros", "entrepot"]
        ).select_related("superviseur", "user")

        if type_agent_filter:
            agents = agents.filter(type_agent=type_agent_filter)

        mamies = []
        gros = []
        superviseurs = []

        total_global = Decimal("0.00")

        for agent in agents:

            # ---------------- MAMY ----------------
            if agent.type_agent == "terrain":
                calc = CalculatorSalaire.calcul_salaire_mamy(
                    agent, date_debut, date_fin
                )

                ligne = {
                    "agent": agent,
                    "superviseur": agent.superviseur,
                    "kilo_total": calc["kilo_total"],
                    "salaire_base": calc["salaire_base"],
                    "incentive": calc["incentive"],
                    "salaire_total": calc["salaire_base"] + calc["incentive"],
                }

                mamies.append(ligne)
                total_global += ligne["salaire_total"]

            # ---------------- AGENT GROS ----------------
            elif agent.type_agent == "agent_gros":
                calc = CalculatorSalaire.calcul_salaire_gros(
                    agent, date_debut, date_fin
                )

                ligne = {
                    "agent": agent,
                    "incentive": calc["incentive"],
                    "cartons_total": calc["cartons_total"],
                    "salaire_total": calc["incentive"],
                }

                gros.append(ligne)
                total_global += ligne["salaire_total"]

            # ---------------- SUPERVISEUR ----------------
            elif agent.type_agent == "entrepot":
                calc = CalculatorSalaire.calcul_salaire_superviseur(
                    agent, date_debut, date_fin
                )

                ligne = {
                    "agent": agent,
                    "kilo_total_mamies": calc["kilo_total_mamies"],
                    "salaire_base": calc["salaire_base"],
                    "dotation": calc["dotation"],
                    "bonus": calc["bonus"],
                    "salaire_total": (
                        calc["salaire_base"] +
                        calc["dotation"] +
                        calc["bonus"]
                    ),
                }

                superviseurs.append(ligne)
                total_global += ligne["salaire_total"]

        return {
            "mamies": mamies,
            "gros": gros,
            "superviseurs": superviseurs,
            "total_global": total_global,
        }
