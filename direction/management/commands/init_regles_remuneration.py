from django.core.management.base import BaseCommand
from decimal import Decimal
from core.models import RegleSalaire  

class Command(BaseCommand):
    help = "Initialise les règles de rémunération"

    def handle(self, *args, **options):
        RegleSalaire.objects.update_or_create(
            type_agent="entrepot",
            defaults={"dotation_fonction": Decimal("15000")}
        )

        RegleSalaire.objects.update_or_create(
            type_agent="terrain",
            defaults={"incentive_par_kg": Decimal("25")}
        )

        RegleSalaire.objects.update_or_create(
            type_agent="agent_gros",
            defaults={"incentive_par_carton": Decimal("250")}
        )

        self.stdout.write(self.style.SUCCESS("✅ Règles de rémunération initialisées"))
