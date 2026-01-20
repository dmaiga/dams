from django.db import transaction
from decimal import Decimal
from core.models import Agent, Salaire
from paie.services.salaire_calculator import CalculatorSalaire


class SalaireGenerationService:
    """
    Génération DÉFINITIVE des salaires sur une période
    """

    @staticmethod
    @transaction.atomic
    def generate(date_debut, date_fin):

        # 🔒 Sécurité : pas de double génération
        if Salaire.objects.filter(
            date_debut=date_debut,
            date_fin=date_fin
        ).exists():
            raise ValueError("Les salaires de cette période sont déjà générés.")

        agents = Agent.objects.filter(
            est_actif=True,
            type_agent__in=["terrain", "agent_gros", "entrepot"]
        )

        salaires_crees = []

        for agent in agents:

            if agent.type_agent == "terrain":
                calc = CalculatorSalaire.calcul_salaire_mamy(agent, date_debut, date_fin)

            elif agent.type_agent == "agent_gros":
                calc = CalculatorSalaire.calcul_salaire_gros(agent, date_debut, date_fin)

            elif agent.type_agent == "entrepot":
                calc = CalculatorSalaire.calcul_salaire_superviseur(agent, date_debut, date_fin)

            else:
                continue

            incentive = (
                calc.get("incentive", Decimal("0.00")) +
                calc.get("bonus", Decimal("0.00"))
            )

            salaire = Salaire.objects.create(
                agent=agent,
                date_debut=date_debut,
                date_fin=date_fin,
                salaire_base=calc.get("salaire_base", Decimal("0.00")),
                incentive=incentive,
                salaire_total=calc["salaire_total"],
            )

            salaires_crees.append(salaire)

        return salaires_crees
