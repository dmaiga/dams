from datetime import datetime

from django.core.management.base import BaseCommand
from core.models import LotEntrepot


class Command(BaseCommand):
    help = "Remet quantite_restante à 0 pour les lots reçus jusqu'à une date donnée (défaut : 31/07/2026)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default="2026-07-31",
            help="Date limite (incluse), format YYYY-MM-DD",
        )

    def handle(self, *args, **options):
        date_limite = datetime.strptime(options["date"], "%Y-%m-%d").date()

        lots = LotEntrepot.objects.filter(
            date_reception__date__lte=date_limite,
            quantite_restante__gt=0,
        )

        nb = lots.count()
        if nb == 0:
            self.stdout.write(self.style.WARNING(
                f"Aucun lot avec du stock restant reçu jusqu'au {date_limite}."
            ))
            return

        lots.update(quantite_restante=0)

        self.stdout.write(self.style.SUCCESS(
            f"✅ {nb} lot(s) reçu(s) jusqu'au {date_limite} : quantite_restante remise à 0."
        ))
