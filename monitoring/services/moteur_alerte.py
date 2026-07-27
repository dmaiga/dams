from core.models import DetailDistribution, RecouvrementSuperviseur
from finance.services import lister_soldes_superviseurs, solde_superviseur
from monitoring.providers.telegram import TelegramProvider
from monitoring.services.deduplication_service import AlerteDeduplicationService
from surveillance.services.prix_service import PrixSurveillanceService
from surveillance.services.stock_age_service import StockAgeService


class AlerteMoteur:
    """Évalue les 4 alertes MVP (5 règles) du Chantier 3 (docs/sprints/sprint-05.md).

    Lecture seule sur finance/surveillance — écriture uniquement sur Alerte (core),
    via AlerteDeduplicationService. Aucun signal, aucune vue.
    """

    @staticmethod
    def evaluer_solde_superviseur():
        superviseurs_en_alerte = []
        superviseurs_persistants = []

        for item in lister_soldes_superviseurs():
            superviseur = item["superviseur"]

            if item["alerte"]:
                superviseurs_en_alerte.append({"superviseur": superviseur.user})
                alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                    type_alerte="solde",
                    defaults={
                        "niveau": "info",
                        "message": (
                            f"Solde du superviseur {superviseur} : {item['solde']} FCFA "
                            "(réconciliation matinale, seuil dépassé)."
                        ),
                    },
                    superviseur=superviseur.user,
                )
                if doit_envoyer:
                    TelegramProvider.send(alerte)

            derniers_cycles = list(
                RecouvrementSuperviseur.objects
                .filter(superviseur=superviseur)
                .order_by("-date_recouvrement")[:3]
            )
            trois_cycles_residuels = len(derniers_cycles) == 3 and all(
                solde_superviseur(superviseur, date_fin=cycle.date_recouvrement.date())["solde"] > 0
                for cycle in derniers_cycles
            )
            if trois_cycles_residuels:
                superviseurs_persistants.append({"superviseur": superviseur.user})
                alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                    type_alerte="solde_persistant",
                    defaults={
                        "niveau": "critique",
                        "message": (
                            f"Solde persistant chez {superviseur} : encore débiteur après "
                            "3 cycles de remise consécutifs."
                        ),
                    },
                    superviseur=superviseur.user,
                )
                if doit_envoyer:
                    TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("solde", superviseurs_en_alerte)
        AlerteDeduplicationService.cloturer_si_resolue("solde_persistant", superviseurs_persistants)

    @staticmethod
    def evaluer_stock_ancien():
        lots_actifs = []
        for lot_data in StockAgeService.lots_stock_dormant():
            lot = lot_data["lot"]
            lots_actifs.append({"lot": lot})
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock",
                defaults={
                    "niveau": "warning",
                    "message": f"Lot {lot} dormant depuis plus de 14 jours.",
                    "produit": lot_data.get("produit"),
                },
                lot=lot,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("stock", lots_actifs)

    @staticmethod
    def evaluer_variation_prix():
        lots_actifs = []
        for item in PrixSurveillanceService.ventes_a_perte():
            lot = item["lot"]
            lots_actifs.append({"lot": lot})
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="prix",
                defaults={
                    "niveau": "critique",
                    "message": (
                        f"Vente(s) sous le prix d'achat pour le lot {lot} ({item['produit']}) — "
                        f"prix d'achat {item['prix_achat']} FCFA, prix de vente minimum constaté "
                        f"{item['prix_min']} FCFA."
                    ),
                    "produit": item["produit"],
                },
                lot=lot,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("prix", lots_actifs)

    @staticmethod
    def evaluer_baisse_activite():
        agents_actifs = []
        for agent_data in StockAgeService.agents_sans_vente_recente():
            agent = agent_data["agent"]
            if agent.type_agent == "entrepot":
                # Un superviseur vend occasionnellement, ce n'est pas son activité
                # principale — cette règle cible les agents dont la vente est le métier.
                continue

            distribution = DetailDistribution.objects.filter(
                pk=agent_data["distribution_id"]
            ).first()
            agents_actifs.append({"agent": agent.user})
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="activite",
                defaults={
                    "niveau": "warning",
                    "message": f"Agent {agent} sans vente depuis plus de 2 jours.",
                    "distribution": distribution,
                },
                agent=agent.user,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("activite", agents_actifs)
