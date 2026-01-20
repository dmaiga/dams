from decimal import Decimal
from core.models import Agent
from paie.services.salaire_calculator import CalculatorSalaire


class SalaireListeService:
    """
    Service Direction – Liste des salaires à verser (LECTURE SEULE)
    """

    @staticmethod
    def get_salaires(date_debut, date_fin, type_agent_filter=""):
        # ----------------------------
        # FILTRAGE DES AGENTS
        # ----------------------------
        agents = Agent.objects.filter(
            est_actif=True,
            type_agent__in=["terrain", "agent_gros", "entrepot"]
        )
        
        # Appliquer le filtre si spécifié
        if type_agent_filter:
            agents = agents.filter(type_agent=type_agent_filter)
        
        agents = agents.select_related("superviseur", "user")

        lignes = []
        total_global = Decimal("0.00")

        for agent in agents:
            # ... (le reste de votre code reste identique) ...
            
            # ----------------------------
            # CALCUL CENTRALISÉ
            # ----------------------------
            if agent.type_agent == "terrain":
                calc = CalculatorSalaire.calcul_salaire_mamy(
                    agent, date_debut, date_fin
                )
                salaire_base = calc["salaire_base"]
                incentive = calc["incentive"]
                bonus = Decimal("0.00")

            elif agent.type_agent == "agent_gros":
                calc = CalculatorSalaire.calcul_salaire_gros(
                    agent, date_debut, date_fin
                )
                salaire_base = calc.get("salaire_base", Decimal("0.00"))
                incentive = calc.get("incentive", Decimal("0.00"))
                bonus = Decimal("0.00")

            elif agent.type_agent == "entrepot":
                calc = CalculatorSalaire.calcul_salaire_superviseur(
                    agent, date_debut, date_fin
                )
                salaire_base = calc["salaire_base"]
                incentive = calc["dotation"]
                bonus = calc["bonus"]
            else:
                continue

            salaire_total = salaire_base + incentive + bonus
            total_global += salaire_total

            # ----------------------------
            # LIGNE SALAIRE
            # ----------------------------
            lignes.append({
                "agent": agent,
                "type_agent": agent.type_agent,
                "superviseur": agent.superviseur,
                "salaire_base": salaire_base,
                "incentive": incentive,
                "bonus": bonus,
                "salaire_total": salaire_total,
            })

        return {
            "salaires": lignes,
            "total_global": total_global,
        }