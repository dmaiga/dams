from django.core.management.base import BaseCommand
from decimal import Decimal
from core.models import Agent

class Command(BaseCommand):
    help = "Initialise les salaires de base des agents"

    def handle(self, *args, **options):

        updated_terrain = Agent.objects.filter(
            type_agent="terrain",
            est_actif=True
        ).update(
            salaire_base_personnel=Decimal("20000")
        )

        updated_superviseurs = Agent.objects.filter(
            type_agent="entrepot",
            est_actif=True
        ).update(
            salaire_base_personnel=Decimal("50000")
        )

        updated_gros = Agent.objects.filter(
            type_agent="agent_gros",
            est_actif=True
        ).update(
            salaire_base_personnel=Decimal("30000")
        )

        self.stdout.write(self.style.SUCCESS(
            f"✅ Salaires initialisés "
            f"(terrain={updated_terrain}, "
            f"superviseurs={updated_superviseurs}, "
            f"gros={updated_gros})"
        ))
