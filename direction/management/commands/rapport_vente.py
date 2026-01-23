from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from direction.services.rapport_ventes_service import RapportVentesService
from collections import defaultdict

JOURS_FR = {
    0: "lundi",
    1: "mardi",
    2: "mercredi",
    3: "jeudi",
    4: "vendredi",
    5: "samedi",
    6: "dimanche",
}


class Command(BaseCommand):
    help = "Génère un rapport des ventes par agent actif sur une période donnée"

    def add_arguments(self, parser):
        parser.add_argument("--date_debut", required=True, help="YYYY-MM-DD")
        parser.add_argument("--date_fin", required=True, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        # 1️⃣ Parsing des dates
        date_debut = datetime.strptime(options["date_debut"], "%Y-%m-%d").date()
        date_fin = datetime.strptime(options["date_fin"], "%Y-%m-%d").date()

        # 2️⃣ Tous les jours de la période
        jours_attendus = set()
        current_date = date_debut
        while current_date <= date_fin:
            jours_attendus.add(current_date)
            current_date += timedelta(days=1)

        # 3️⃣ Récupération du rapport
        rapport = RapportVentesService.rapport_agents(date_debut, date_fin)

        self.stdout.write(
            f"Rapport des ventes du {date_debut} au {date_fin}\n"
        )

        agents = defaultdict(list)

        for r in rapport:
            agent = f"{r['agent__user__first_name']} {r['agent__user__last_name']}"
            agents[agent].append(r)

        # 4️⃣ Affichage par agent
        for agent, ventes in agents.items():
            self.stdout.write("=" * 100)
            self.stdout.write(f"AGENT : {agent}")
            self.stdout.write("-" * 100)

            jours_vendus = set()

            for v in ventes:
                jour_vente = v["date_vente__date"]
                jours_vendus.add(jour_vente)

                self.stdout.write(
                    f"{jour_vente} | "
                    f"{v['detail_distribution__lot__produit__nom']} | "
                    f"{v['total_quantite']} | "
                    
                )

            # 5️⃣ Jours manquants
            jours_manquants = sorted(jours_attendus - jours_vendus)

            self.stdout.write("-" * 100)
            self.stdout.write(
                f"Jours de vente : {len(jours_vendus)} / "
                f"{len(jours_attendus)}"
            )

            if jours_manquants:
                self.stdout.write("Jours sans vente :")
                for jour in jours_manquants:
                    nom_jour = JOURS_FR[jour.weekday()]
                    self.stdout.write(f" - {nom_jour} {jour.strftime('%d/%m/%Y')}")
            else:
                self.stdout.write("Jours sans vente : AUCUN")

            self.stdout.write("\n")
