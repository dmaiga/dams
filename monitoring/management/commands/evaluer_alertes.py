from django.core.management.base import BaseCommand

from monitoring.services.moteur_alerte import AlerteMoteur


class Command(BaseCommand):
    help = "Évalue les alertes MVP (solde, solde persistant, stock, prix, activité) et notifie via Telegram."

    def handle(self, *args, **options):
        AlerteMoteur.evaluer_solde_superviseur()
        AlerteMoteur.evaluer_stock_ancien()
        AlerteMoteur.evaluer_variation_prix()
        AlerteMoteur.evaluer_baisse_activite()
        self.stdout.write(self.style.SUCCESS("Alertes évaluées."))
