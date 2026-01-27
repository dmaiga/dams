from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date
from core.models import Agent, Recouvrement

class Command(BaseCommand):
    help = "Transfère les recouvrements selon les nouveaux superviseurs"

    def handle(self, *args, **options):
        DATE_EFFET = date(2026, 1, 1)

        ancien = Agent.objects.get(user__username="abdoulaye.kone", type_agent="entrepot")
        nouveau = Agent.objects.get(user__username="sidibe.mankoulako", type_agent="entrepot")

        agents = Agent.objects.filter(
            type_agent="terrain",
            superviseur=nouveau,
            est_actif=True
        )

        recouvrements = Recouvrement.objects.filter(
            superviseur=ancien,
            agent__in=agents,
            date_recouvrement__date__gte=DATE_EFFET
        )

        with transaction.atomic():
            recouvrements.update(superviseur=nouveau)

        self.stdout.write(self.style.SUCCESS(
            f"✅ {recouvrements.count()} recouvrements transférés"
        ))
