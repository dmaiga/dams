from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from datetime import datetime
import os

from utils.calendrier import derniers_jours_ouvres
from utils.email_utils import envoyer_rapport_email
from django.conf import settings


class Command(BaseCommand):
    help = "Génère et envoie automatiquement le rapport de ventes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date_debut",
            help="Date de début YYYY-MM-DD (optionnel)"
        )
        parser.add_argument(
            "--date_fin",
            help="Date de fin YYYY-MM-DD (optionnel)"
        )

    def handle(self, *args, **options):
        # =====================================
        # 1️⃣ DÉTERMINATION DE LA PÉRIODE
        # =====================================
        date_debut_opt = options.get("date_debut")
        date_fin_opt = options.get("date_fin")

        if date_debut_opt and date_fin_opt:
            try:
                date_debut = datetime.strptime(date_debut_opt, "%Y-%m-%d").date()
                date_fin = datetime.strptime(date_fin_opt, "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(
                    "❌ Format invalide. Utilisez YYYY-MM-DD"
                )

            if date_debut > date_fin:
                raise CommandError(
                    "❌ date_debut ne peut pas être après date_fin"
                )

            self.stdout.write(
                f"📅 Période manuelle : {date_debut} → {date_fin}"
            )

        elif not date_debut_opt and not date_fin_opt:
            date_debut, date_fin = derniers_jours_ouvres(nb_jours=2)
            self.stdout.write(
                f"📅 Période automatique : {date_debut} → {date_fin}"
            )
        

        else:
            raise CommandError(
                "❌ Vous devez fournir date_debut ET date_fin, ou aucun des deux."
            )

        # =====================================
        # 2️⃣ CHEMIN DE SAUVEGARDE
        # =====================================
        year = date_fin.year
        mois = date_fin.strftime("%B").lower()

        base_dir = os.path.join(
            settings.BASE_DIR,
            "reports",
            "ventes",
            str(year),
            mois
        )
        os.makedirs(base_dir, exist_ok=True)

        filename = f"rapport_ventes_{date_debut}_{date_fin}.pdf"
        fichier_path = os.path.join(base_dir, filename)

        # =====================================
        # 3️⃣ GÉNÉRATION DU RAPPORT
        # =====================================
        call_command(
            "rapport_vente",
            date_debut=date_debut.strftime("%Y-%m-%d"),
            date_fin=date_fin.strftime("%Y-%m-%d"),
            format="pdf",
            output=fichier_path 
        )

        # =====================================
        # 4️⃣ ENVOI EMAIL
        # =====================================
        envoyer_rapport_email(
            fichier_path=fichier_path,
            sujet="Rapport des ventes",
            message=(
                "Bonjour,\n\n"
                "Veuillez trouver en pièce jointe le rapport des ventes.\n\n"
                f"Période : {date_debut} → {date_fin}\n\n"
                "Cordialement."
            ),
            destinataires=[
                "mdmaiga01@gmail.com",
 #               "fofanaaminata764@gmail.com",
#                "s.diarra@antares-rh.com"
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"📧 Rapport généré et envoyé : {fichier_path}"
            )
        )
