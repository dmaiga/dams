from decimal import Decimal
from core.models import Agent
from paie.services.salaire_calculator import CalculatorSalaire


class SalaireListeService:
    """
    Service Direction – Liste des salaires à verser (lecture seule)
    """

    @staticmethod
    def get_salaires(date_debut, date_fin):
        agents = Agent.objects.filter(
            est_actif=True,
            type_agent__in=["terrain", "agent_gros", "entrepot"]
        ).select_related("superviseur", "user")

        data = []
        total_global = Decimal("0")

        for agent in agents:

            # ----------------------------
            # CALCUL SELON TYPE
            # ----------------------------
            if agent.type_agent == "terrain":
                result = CalculatorSalaire.calcul_salaire_mamy(
                    agent, date_debut, date_fin
                )

                salaire_base = result["salaire_base"]
                incentive = result["incentive"]
                salaire_total = result["salaire_total"]

            elif agent.type_agent == "agent_gros":
                result = CalculatorSalaire.calcul_salaire_gros(
                    agent, date_debut, date_fin
                )

                salaire_base = Decimal("0")
                incentive = Decimal("0")
                salaire_total = result["salaire_total"]

            elif agent.type_agent == "entrepot":
                result = CalculatorSalaire.calcul_salaire_superviseur(
                    agent, date_debut, date_fin
                )

                salaire_base = result["salaire_base"] + result["dotation"]
                incentive = result["bonus"]
                salaire_total = result["salaire_total"]

            else:
                continue

            total_global += salaire_total

            data.append({
                "agent": agent,
                "type_agent": agent.type_agent,
                "superviseur": agent.superviseur,
                "salaire_base": salaire_base,
                "incentive": incentive,
                "salaire_total": salaire_total,
            })

        return {
            "salaires": data,
            "total_global": total_global,
        }
