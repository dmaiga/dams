from django.core.management.base import BaseCommand
from datetime import datetime
import os

from direction.services.rapport_ventes_service import RapportVentesService
from direction.exports.rapport_word import generer_rapport_ventes_word
from direction.exports.rapport_pdf import generer_rapport_ventes_pdf
from utils.paths import chemin_rapport


class Command(BaseCommand):
    help = "Exporte un rapport de ventes (Word ou PDF)"

    def add_arguments(self, parser):
        parser.add_argument("--date_debut", required=True)
        parser.add_argument("--date_fin", required=True)
        parser.add_argument(
            "--format",
            choices=["word", "pdf"],
            default="pdf"
        )
        parser.add_argument(
            "--output",
            help="Chemin complet du fichier de sortie (optionnel)"
        )

    def handle(self, *args, **options):
        # ===============================
        # 1️⃣ Dates
        # ===============================
        date_debut = datetime.strptime(options["date_debut"], "%Y-%m-%d").date()
        date_fin = datetime.strptime(options["date_fin"], "%Y-%m-%d").date()

        # ===============================
        # 2️⃣ Données
        # ===============================
        rapport = RapportVentesService.rapport_agents(date_debut, date_fin)

        # ===============================
        # 3️⃣ Chemin par défaut
        # ===============================
        base_dir = "rapports"
        dossier = chemin_rapport(base_dir, date_debut)

        ext = "docx" if options["format"] == "word" else "pdf"
        filename = f"rapport_ventes_{date_debut}_{date_fin}.{ext}"
        filepath = os.path.join(dossier, filename)

        # ===============================
        # 4️⃣ Output final
        # ===============================
        output = options.get("output") or filepath
        os.makedirs(os.path.dirname(output), exist_ok=True)

        # ===============================
        # 5️⃣ Génération (écrase si existe)
        # ===============================
        if options["format"] == "word":
            generer_rapport_ventes_word(
                rapport, date_debut, date_fin, output
            )
        else:
            generer_rapport_ventes_pdf(
                rapport, date_debut, date_fin, output
            )

        self.stdout.write(
            self.style.SUCCESS(f"📄 Rapport généré : {output}")
        )
