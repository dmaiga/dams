# app/management/commands/desactiver_stagiaires_expires.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Agent

class Command(BaseCommand):
    help = "Désactive les stagiaires dont la période est expirée"

    def handle(self, *args, **options):
        stagiaires_expires = Agent.objects.filter(type_agent='stagiaire', date_expiration__lt=timezone.now())
        count = 0
        for agent in stagiaires_expires:
            if agent.user.is_active:
                agent.user.is_active = False
                agent.user.save(update_fields=['is_active'])
                count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} stagiaires désactivés automatiquement."))
