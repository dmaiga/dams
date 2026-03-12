from decimal import Decimal
from core.models import Agent, Salaire
from paie.services.salaire_calculator import CalculatorSalaire

from django.utils import timezone
from datetime import timedelta




class SalaireListeService:
    """
    Service Direction – Liste des salaires à verser
    
    MODE 1 (use_db=False): Calcule en live depuis les Ventes (PREVIEW)
    MODE 2 (use_db=True): Lit depuis table Salaire en BD (HISTORIQUE) ✅
    """

    @staticmethod
    def get_salaires(date_debut, date_fin, type_agent_filter="", use_db=False):
        """
        Récupère la liste des salaires pour une période.
        
        Args:
            use_db=False: Recalcule depuis Ventes (avant génération)
            use_db=True: Lit depuis Salaire en BD (après génération) ✅
        """
        if use_db:
            # ============================================
            # MODE 2: LECTURE DEPUIS BD (après génération)
            # ============================================
            salaires = Salaire.objects.filter(
                date_debut=date_debut,
                date_fin=date_fin
            ).select_related("agent__superviseur", "agent__user")

            if type_agent_filter:
                salaires = salaires.filter(agent__type_agent=type_agent_filter)

            mamies = []
            gros = []
            superviseurs = []

            total_mamy_salaire_base = Decimal("0.00")
            total_mamy_incentive = Decimal("0.00")
            total_mamy_general = Decimal("0.00")

            total_gros_incentive = Decimal("0.00")
            total_gros_general = Decimal("0.00")

            total_sup_salaire_base = Decimal("0.00")
            total_sup_bonus = Decimal("0.00")
            total_sup_general = Decimal("0.00")

            total_global = Decimal("0.00")

            for salaire in salaires:
                agent = salaire.agent

                if agent.type_agent == "terrain":
                    ligne = {
                        "agent": agent,
                        "superviseur": agent.superviseur,
                        "salaire_base": salaire.salaire_base,
                        "incentive": salaire.incentive,
                        "salaire_total": salaire.salaire_total,
                        "valide": salaire.valide,  # ✅ Affiche si validé
                    }
                    mamies.append(ligne)
                    total_mamy_salaire_base += salaire.salaire_base
                    total_mamy_incentive += salaire.incentive
                    total_mamy_general += salaire.salaire_total
                    total_global += salaire.salaire_total

                elif agent.type_agent == "agent_gros":
                    ligne = {
                        "agent": agent,
                        "salaire_total": salaire.salaire_total,
                        "incentive": salaire.incentive,
                        "valide": salaire.valide,
                    }
                    gros.append(ligne)
                    total_gros_incentive += salaire.incentive
                    total_gros_general += salaire.salaire_total
                    total_global += salaire.salaire_total

                elif agent.type_agent == "entrepot":
                    ligne = {
                        "agent": agent,
                        "salaire_base": salaire.salaire_base,
                        "incentive": salaire.incentive,
                        "salaire_total": salaire.salaire_total,
                        "valide": salaire.valide,
                    }
                    superviseurs.append(ligne)
                    total_sup_salaire_base += salaire.salaire_base
                    total_sup_bonus += salaire.incentive
                    total_sup_general += salaire.salaire_total
                    total_global += salaire.salaire_total

            return {
                "mamies": mamies,
                "gros": gros,
                "superviseurs": superviseurs,
                "is_from_db": True,  # Flag: données figées ✅

                "total_mamy_kilo": Decimal("0.00"),
                "total_mamy_salaire_base": total_mamy_salaire_base,
                "total_mamy_incentive": total_mamy_incentive,
                "total_mamy_general": total_mamy_general,

                "total_gros_cartons": Decimal("0.00"),
                "total_gros_incentive": total_gros_incentive,
                "total_gros_general": total_gros_general,

                "total_sup_kilo_mamies": Decimal("0.00"),
                "total_sup_salaire_base": total_sup_salaire_base,
                "total_sup_dotation": Decimal("0.00"),
                "total_sup_bonus": total_sup_bonus,
                "total_sup_general": total_sup_general,

                "total_global": total_global,
            }

        # ============================================
        # MODE 1: CALCUL EN LIVE (avant génération)
        # ============================================


        agents = Agent.objects.filter(
            est_actif=True,
            type_agent__in=["terrain", "agent_gros", "entrepot"]
        ).select_related("superviseur", "user")

        if type_agent_filter:
            agents = agents.filter(type_agent=type_agent_filter)

        mamies = []
        gros = []
        superviseurs = []

        # ===============================
        # TOTAUX MAMIES
        # ===============================
        total_mamy_kilo = Decimal("0.00")
        total_mamy_salaire_base = Decimal("0.00")
        total_mamy_incentive = Decimal("0.00")
        total_mamy_general = Decimal("0.00")

        # ===============================
        # TOTAUX AGENTS GROS
        # ===============================
        total_gros_cartons = Decimal("0.00")
        total_gros_incentive = Decimal("0.00")
        total_gros_general = Decimal("0.00")

        # ===============================
        # TOTAUX SUPERVISEURS
        # ===============================
        total_sup_kilo_mamies = Decimal("0.00")
        total_sup_salaire_base = Decimal("0.00")
        total_sup_dotation = Decimal("0.00")
        total_sup_bonus = Decimal("0.00")
        total_sup_general = Decimal("0.00")

        total_global = Decimal("0.00")

        for agent in agents:

            # ---------------- MAMY ----------------
            if agent.type_agent == "terrain":
                calc = CalculatorSalaire.calcul_salaire_mamy(
                    agent, date_debut, date_fin
                )

                salaire_base = calc["salaire_base"]
                incentive = calc["incentive"]
                salaire_total = salaire_base + incentive

                ligne = {
                    "agent": agent,
                    "superviseur": agent.superviseur,
                    "kilo_total": calc["kilo_total"],

                    "salaire_base": salaire_base,
                    "salaire_base_theorique": calc.get("salaire_base_theorique"),
                    "jours_travailles": calc.get("jours_travailles"),
                    "jours_mois": calc.get("jours_mois"),

                    "incentive": incentive,
                    "salaire_total": salaire_total,
                }


                mamies.append(ligne)

                # ➕ TOTAUX MAMIES
                total_mamy_kilo += calc["kilo_total"]
                total_mamy_salaire_base += salaire_base
                total_mamy_incentive += incentive
                total_mamy_general += salaire_total
                total_global += salaire_total

            # ---------------- AGENT GROS ----------------
            elif agent.type_agent == "agent_gros":
                calc = CalculatorSalaire.calcul_salaire_gros(
                    agent, date_debut, date_fin
                )

                incentive = calc["incentive"]
                cartons = calc["cartons_total"]

                ligne = {
                    "agent": agent,
                    "cartons_total": cartons,
                    "incentive": incentive,
                    "salaire_total": incentive,
                }

                gros.append(ligne)

                # ➕ TOTAUX GROS
                total_gros_cartons += cartons
                total_gros_incentive += incentive
                total_gros_general += incentive
                total_global += incentive

            # ---------------- SUPERVISEUR ----------------
            elif agent.type_agent == "entrepot":
                calc = CalculatorSalaire.calcul_salaire_superviseur(
                    agent, date_debut, date_fin
                )

                salaire_base = calc["salaire_base"]
                dotation = calc["dotation"]
                bonus = calc["bonus"]
                salaire_total = salaire_base + dotation + bonus

                ligne = {
                    "agent": agent,
                    "kilo_total_mamies": calc["kilo_total_mamies"],
                    "salaire_base": salaire_base,
                    "dotation": dotation,
                    "bonus": bonus,
                    "salaire_total": salaire_total,
                }

                superviseurs.append(ligne)

                # ➕ TOTAUX SUPERVISEURS
                total_sup_kilo_mamies += calc["kilo_total_mamies"]
                total_sup_salaire_base += salaire_base
                total_sup_dotation += dotation
                total_sup_bonus += bonus
                total_sup_general += salaire_total
                total_global += salaire_total

        return {
            "mamies": mamies,
            "gros": gros,
            "superviseurs": superviseurs,
            "is_from_db": False,  # Flag: données calculées en live

            # 👩‍🌾 TOTAUX MAMIES
            "total_mamy_kilo": total_mamy_kilo,
            "total_mamy_salaire_base": total_mamy_salaire_base,
            "total_mamy_incentive": total_mamy_incentive,
            "total_mamy_general": total_mamy_general,

            # 📦 TOTAUX GROS
            "total_gros_cartons": total_gros_cartons,
            "total_gros_incentive": total_gros_incentive,
            "total_gros_general": total_gros_general,

            # 🏢 TOTAUX SUPERVISEURS
            "total_sup_kilo_mamies": total_sup_kilo_mamies,
            "total_sup_salaire_base": total_sup_salaire_base,
            "total_sup_dotation": total_sup_dotation,
            "total_sup_bonus": total_sup_bonus,
            "total_sup_general": total_sup_general,

            # 🌍 GLOBAL
            "total_global": total_global,
        }
