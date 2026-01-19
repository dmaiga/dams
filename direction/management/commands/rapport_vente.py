from django.core.management.base import BaseCommand
from datetime import datetime
from direction.services.rapport_ventes_service import RapportVentesService


class Command(BaseCommand):
    help = "Génère un rapport des ventes par agent actif sur une période donnée"

    def add_arguments(self, parser):
        parser.add_argument("--date_debut", required=True, help="YYYY-MM-DD")
        parser.add_argument("--date_fin", required=True, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        date_debut = datetime.strptime(options["date_debut"], "%Y-%m-%d").date()
        date_fin = datetime.strptime(options["date_fin"], "%Y-%m-%d").date()

        rapport = RapportVentesService.rapport_agents(date_debut, date_fin)

        self.stdout.write(
            f"Rapport des ventes du {date_debut} au {date_fin}\n"
        )

        for r in rapport:
            self.stdout.write(
                f"{r['agent__user__first_name']} {r['agent__user__last_name']} | "
                f"{r['detail_distribution__lot__produit__nom']} | "
                f"{r['total_quantite']} | "
                f"{r['nombre_ventes']} ventes"
            )
