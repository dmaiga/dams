# python manage.py cloturer_mois --start 2025-01 --end 2025-06
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction

from core.models import ClotureMensuelle, Agent
from direction.services.cloture_service import calculer_solde_periode


class Command(BaseCommand):
    help = "Clôture un ou plusieurs mois pour tous les superviseurs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            type=str,
            help="Mois de début au format YYYY-MM (ex: 2025-10)"
        )
        parser.add_argument(
            "--end",
            type=str,
            help="Mois de fin au format YYYY-MM (ex: 2025-12)"
        )

    def handle(self, *args, **options):
        start = options.get("start")
        end = options.get("end")

        # 🔁 Détermination de la plage de mois
        if start and end:
            start_year, start_month = map(int, start.split("-"))
            end_year, end_month = map(int, end.split("-"))

            current = date(start_year, start_month, 1)
            end_date = date(end_year, end_month, 1)

            months = []
            while current <= end_date:
                months.append(current)
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

        else:
            # 🔹 Mode automatique : mois précédent
            today = timezone.now().date()
            first_of_current_month = today.replace(day=1)
            last_month_end = first_of_current_month - timedelta(days=1)
            months = [last_month_end.replace(day=1)]

        superviseurs = Agent.objects.filter(type_agent="entrepot", est_actif=True)

        if not superviseurs.exists():
            self.stdout.write(self.style.WARNING(" Aucun superviseur trouvé"))
            return

        for month_start in months:
            date_debut = month_start
            next_month = (
                date(month_start.year + 1, 1, 1)
                if month_start.month == 12
                else date(month_start.year, month_start.month + 1, 1)
            )
            date_fin = next_month - timedelta(days=1)

            annee = date_debut.year
            mois = date_debut.month

            self.stdout.write(
                self.style.NOTICE(
                    f"\n Clôture {mois:02d}/{annee} ({date_debut} -> {date_fin})"
                )
            )

            for superviseur in superviseurs:
                with transaction.atomic():

                    cloture, _ = ClotureMensuelle.objects.update_or_create(
                        superviseur=superviseur,
                        annee=annee,
                        mois=mois,
                        defaults={
                            "date_debut_periode": date_debut,
                            "date_fin_periode": date_fin,
                            "solde_ouverture": self._get_solde_ouverture(superviseur),
                            "solde_cloture": Decimal("0.00"),
                            "est_cloture": False,
                        }
                    )

                    if cloture.est_cloture:
                        self.stdout.write(
                            self.style.WARNING(
                                f"{superviseur} : déjà clôturé"
                            )
                        )
                        continue

                    data = calculer_solde_periode(
                        superviseur=superviseur,
                        date_debut=date_debut,
                        date_fin=date_fin,
                        solde_ouverture=cloture.solde_ouverture
                    )

                    cloture.solde_cloture = data["solde_cloture"]
                    cloture.est_cloture = True
                    cloture.date_cloture = timezone.now()
                    cloture.save()

                    superviseur.remettre_solde_operationnel_a_zero(cloture=cloture)

                    self.stdout.write(
                        self.style.SUCCESS(
                            f" {superviseur} | Solde clôturé = {cloture.solde_cloture}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS("\n Clôture terminée"))

    def _get_solde_ouverture(self, superviseur):
        derniere = ClotureMensuelle.objects.filter(
            superviseur=superviseur,
            est_cloture=True
        ).order_by("-date_fin_periode").first()

        return derniere.solde_cloture if derniere else Decimal("0.00")
