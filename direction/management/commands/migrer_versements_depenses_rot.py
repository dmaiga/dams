from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import date
from core.models import VersementBancaire, Depense, Agent


class Command(BaseCommand):
    help = (
        "Migre les versements et dépenses d’un superviseur "
        "vers un agent ROT à partir d’une date de bascule"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date-bascule",
            type=str,
            default="2026-01-01",
            help="Date de bascule au format YYYY-MM-DD (défaut: 2026-01-01)"
        )
        parser.add_argument(
            "--ancien-superviseur",
            type=str,
            default="abdoulaye.kone",
            help="Username de l’ancien superviseur"
        )
        parser.add_argument(
            "--rot",
            type=str,
            default="kone.abdoulaye",
            help="Username du nouvel agent ROT"
        )

    def handle(self, *args, **options):

        date_bascule = date.fromisoformat(options["date_bascule"])
        ancien_username = options["ancien_superviseur"]
        rot_username = options["rot"]

        try:
            ancien_superviseur = Agent.objects.get(
                user__username=ancien_username
            )
        except Agent.DoesNotExist:
            raise CommandError(f"Ancien superviseur introuvable: {ancien_username}")

        try:
            rot = Agent.objects.get(
                user__username=rot_username,
                type_agent="rot"
            )
        except Agent.DoesNotExist:
            raise CommandError(f"Agent ROT introuvable: {rot_username}")

        self.stdout.write(
            f"🔁 Migration depuis {ancien_superviseur.full_name} "
            f"→ ROT {rot.full_name} "
            f"(à partir du {date_bascule})"
        )

        with transaction.atomic():

            # =====================================
            # 1️⃣ MIGRATION DES VERSEMENTS
            # =====================================
            versements = VersementBancaire.objects.filter(
                superviseur=ancien_superviseur,
                date_versement_reelle__date__gte=date_bascule
            )

            self.stdout.write(f"📦 {versements.count()} versements à migrer")

            updated_versements = versements.update(
                effectue_par=rot
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Versements migrés : {updated_versements}"
                )
            )

            # =====================================
            # 2️⃣ MIGRATION DES DÉPENSES LIÉES
            # =====================================
            depenses = Depense.objects.filter(
                versement__in=versements,
                date_depense__date__gte=date_bascule
            )

            self.stdout.write(f"💸 {depenses.count()} dépenses à migrer")

            updated_depenses = depenses.update(
                effectue_par=rot
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Dépenses migrées : {updated_depenses}"
                )
            )

        self.stdout.write(self.style.SUCCESS("🎉 Migration ROT terminée avec succès"))
