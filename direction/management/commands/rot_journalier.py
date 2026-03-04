# core/management/commands/rot_journalier.py
#python manage.py rot_journalier kone.abdoulaye 2026-02-01 2026-02-20

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import datetime, timedelta

from core.models import (
    Agent,
    RecouvrementSuperviseur,
    VersementBancaire,
    Depense,
)


class Command(BaseCommand):
    help = "Journal financier ROT complet (audit caisse)"

    # --------------------------------------------------
    # ARGUMENTS
    # --------------------------------------------------
    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument("date_debut", type=str)
        parser.add_argument("date_fin", type=str)

    # --------------------------------------------------
    # EXECUTION
    # --------------------------------------------------
    def handle(self, *args, **options):

        username = options["username"]

        debut = datetime.strptime(options["date_debut"], "%Y-%m-%d").date()
        fin = datetime.strptime(options["date_fin"], "%Y-%m-%d").date()

        # 🔎 ROT
        try:
            rot = Agent.objects.select_related("user").get(
                user__username=username
            )
        except Agent.DoesNotExist:
            self.stdout.write(self.style.ERROR("ROT introuvable"))
            return

        # --------------------------------------------------
        # SOLDE INITIAL (AVANT PERIODE)
        # --------------------------------------------------
        recu_initial = RecouvrementSuperviseur.objects.filter(
            rot=rot,
            date_recouvrement__date__lt=debut
        ).aggregate(total=Coalesce(Sum("montant"), Decimal("0")))["total"]

        verse_initial = VersementBancaire.objects.filter(
            effectue_par=rot,
            date_versement_reelle__date__lt=debut
        ).aggregate(total=Coalesce(Sum("montant_vente"), Decimal("0")))["total"]

        depense_initial = Depense.objects.filter(
            effectue_par=rot,
            date_depense__lt=debut
        ).aggregate(total=Coalesce(Sum("montant"), Decimal("0")))["total"]

        cumul = recu_initial - verse_initial - depense_initial

        # --------------------------------------------------
        # PRELOAD PERIODE (PERFORMANCE)
        # --------------------------------------------------
        periode_recus = RecouvrementSuperviseur.objects.filter(
            rot=rot,
            date_recouvrement__date__range=(debut, fin)
        )

        periode_versements = VersementBancaire.objects.filter(
            effectue_par=rot,
            date_versement_reelle__date__range=(debut, fin)
        )

        periode_depenses = Depense.objects.filter(
            effectue_par=rot,
            date_depense__range=(debut, fin)
        )

        # --------------------------------------------------
        # AFFICHAGE ENTETE
        # --------------------------------------------------
        self.stdout.write("")
        self.stdout.write(f"Journal ROT : {rot.user.username}")
        self.stdout.write(f"SOLDE INITIAL AVANT {debut} : {cumul:.0f}")
        self.stdout.write(
            "DATE        | RECU      | DEPENSE   | VERSE     | SOLDE J | CUMUL"
        )
        self.stdout.write("-" * 85)

        # --------------------------------------------------
        # TOTAUX
        # --------------------------------------------------
        total_recu = Decimal("0")
        total_depense = Decimal("0")
        total_verse = Decimal("0")

        anomalies = []

        current = debut

        # --------------------------------------------------
        # BOUCLE JOUR PAR JOUR
        # --------------------------------------------------
        while current <= fin:

            recu = periode_recus.filter(
                date_recouvrement__date=current
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]

            verse = periode_versements.filter(
                date_versement_reelle__date=current
            ).aggregate(
                total=Coalesce(Sum("montant_vente"), Decimal("0"))
            )["total"]

            depenses = periode_depenses.filter(
                date_depense=current
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]

            # ---------------- CALCUL ----------------
            solde_jour = recu - verse - depenses
            cumul += solde_jour

            total_recu += recu
            total_depense += depenses
            total_verse += verse

            # ---------------- DETECTION ANOMALIES ----------------
            if cumul < 0:
                anomalies.append(
                    f"{current} -> Cumul negatif ({cumul:.0f})"
                )

            if verse > recu and recu == 0:
                anomalies.append(
                    f"{current} -> Versement sans recouvrement"
                )

            # ---------------- AFFICHAGE ----------------
            self.stdout.write(
                f"{current} | "
                f"{recu:10.0f} | "
                f"{depenses:10.0f} | "
                f"{verse:10.0f} | "
                f"{solde_jour:8.0f} | "
                f"{cumul:8.0f}"
            )

            current += timedelta(days=1)

        # --------------------------------------------------
        # TOTAL FINAL
        # --------------------------------------------------
        self.stdout.write("-" * 85)

        total_solde = total_recu - total_verse - total_depense

        self.stdout.write(
            f"{'TOTAL':10} | "
            f"{total_recu:10.0f} | "
            f"{total_depense:10.0f} | "
            f"{total_verse:10.0f} | "
            f"{total_solde:8.0f} | "
            f"{cumul:8.0f}"
        )

        # --------------------------------------------------
        # ANOMALIES
        # --------------------------------------------------
        if anomalies:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("ANOMALIES DETECTEES"))
            for a in anomalies:
                self.stdout.write(a)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Audit termine "))