# python manage.py generer_salaires_mensuel
# python manage.py generer_salaires_mensuel --mois 2026-06
#
# Rattrape en un seul lancement tous les mois de salaire manquants entre settings.DATE_DEBUT_ROT
# et le mois précédent inclus (le mois en cours, non terminé, est toujours exclu) — décision
# produit du 23/07/2026 : on ne veut plus dépendre d'un clic manuel mensuel pour que le KPI coût
# salaire (bi.vw_rentabilite_globale) soit alimenté, et on veut pouvoir rattraper l'historique en
# une seule commande plutôt que mois par mois. Un mois déjà généré (brouillon ou validé) est
# simplement ignoré (idempotent, sûr à relancer). --mois force un seul mois précis (correction
# ponctuelle) au lieu du rattrapage complet.
# Les salaires générés restent en brouillon (Salaire.valide=False, cf. core.models.Salaire) : en
# cas d'erreur ou d'écart, la correction se fait dans l'admin Django, pas par une régénération
# (SalaireGenerationService.generate() refuse toute régénération dès qu'un salaire existe pour la
# période, brouillon ou validé).
# Prévu pour être invoqué par une tâche planifiée au niveau OS (Task Scheduler / cron externe) :
# ce repo n'a pas d'infra Celery/APScheduler, cf. docs/BACKLOG.md.
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Salaire
from paie.services.salaire_generation_service import SalaireGenerationService


def _premier_jour_mois_suivant(premier_jour):
    return (
        date(premier_jour.year + 1, 1, 1)
        if premier_jour.month == 12
        else date(premier_jour.year, premier_jour.month + 1, 1)
    )


class Command(BaseCommand):
    help = (
        "Rattrape tous les mois de salaire manquants depuis settings.DATE_DEBUT_ROT jusqu'au "
        "mois précédent inclus (mois en cours toujours exclu). --mois génère un seul mois précis."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--mois",
            type=str,
            help="Génère uniquement ce mois précis, au format YYYY-MM (au lieu du rattrapage complet).",
        )

    def handle(self, *args, **options):
        mois_raw = options.get("mois")

        if mois_raw:
            try:
                annee, mois = map(int, mois_raw.split("-"))
                mois_a_generer = [date(annee, mois, 1)]
            except ValueError:
                raise CommandError("Format --mois invalide, attendu YYYY-MM (ex: 2026-06).")
        else:
            premier_jour_mois_courant = timezone.now().date().replace(day=1)
            mois_a_generer = []
            curseur = settings.DATE_DEBUT_ROT.replace(day=1)
            while curseur < premier_jour_mois_courant:
                mois_a_generer.append(curseur)
                curseur = _premier_jour_mois_suivant(curseur)

        if not mois_a_generer:
            self.stdout.write(self.style.WARNING("Aucun mois à générer."))
            return

        for date_debut in mois_a_generer:
            date_fin = _premier_jour_mois_suivant(date_debut) - timedelta(days=1)

            if Salaire.objects.filter(date_debut=date_debut, date_fin=date_fin).exists():
                self.stdout.write(
                    self.style.NOTICE(f"{date_debut} -> {date_fin} : déjà généré, ignoré.")
                )
                continue

            salaires = SalaireGenerationService.generate(date_debut, date_fin)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{date_debut} -> {date_fin} : {len(salaires)} salaires générés (brouillon)."
                )
            )

        self.stdout.write(self.style.SUCCESS("Génération terminée."))
