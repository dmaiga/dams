# agents_stock_dormant.py
"""
Liste, par superviseur, les agents de vente qui détiennent encore des
produits reçus sur une période donnée (cas « stock dormant » côté agent :
produit distribué mais pas encore écoulé).

Exemple :
    python manage.py agents_stock_dormant --date_debut 2026-08-01 --date_fin 2026-08-31
    python manage.py agents_stock_dormant --date_debut 2026-08-01 --date_fin 2026-08-31 --format pdf

Sortie (forme demandée) :

    superviseur A
    agent A
      - aloco reçu le 22/08/2026
      - tomate reçu le 23/08/2026
    agent B
      - aloco reçu le 22/08/2026
    ------------------------------------------------------------
    superviseur B
    agent A
      - huile reçu le 22/08/2026
"""
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from surveillance.services.stock_age_service import StockAgeService
from utils.paths import chemin_rapport

SEPARATEUR = "-" * 60


def _date_fr(valeur):
    """Datetime aware → 'JJ/MM/AAAA' en heure locale."""
    if timezone.is_aware(valeur):
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y")


class Command(BaseCommand):
    help = (
        "Liste par superviseur les agents qui ont encore des produits à leur "
        "disposition (stock dormant), reçus entre --date_debut et --date_fin."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date_debut", required=True, help="Format AAAA-MM-JJ")
        parser.add_argument("--date_fin", required=True, help="Format AAAA-MM-JJ")
        parser.add_argument("--format", choices=["texte", "pdf"], default="texte")
        parser.add_argument("--output", help="Chemin du fichier PDF de sortie (optionnel)")

    def handle(self, *args, **options):
        try:
            date_debut = datetime.strptime(options["date_debut"], "%Y-%m-%d").date()
            date_fin = datetime.strptime(options["date_fin"], "%Y-%m-%d").date()
        except ValueError:
            raise CommandError("Dates invalides — attendu AAAA-MM-JJ.")

        if date_debut > date_fin:
            raise CommandError("--date_debut doit être antérieure ou égale à --date_fin.")

        groupes = StockAgeService.stock_detenu_agents_par_superviseur(date_debut, date_fin)

        if not groupes:
            self.stdout.write(self.style.WARNING(
                "Aucun agent ne détient de produit reçu sur cette période."
            ))
            return

        # Tri : superviseurs nommés d'abord (par nom), « sans superviseur » en dernier.
        groupes.sort(key=lambda g: (
            g["superviseur"] is None,
            g["superviseur"].full_name.lower() if g["superviseur"] else "",
        ))

        if options["format"] == "pdf":
            chemin = self._generer_pdf(groupes, date_debut, date_fin, options.get("output"))
            self.stdout.write(self.style.SUCCESS(f"Rapport généré : {chemin}"))
        else:
            self.stdout.write("\n".join(self._lignes_texte(groupes, date_debut, date_fin)))

    # ------------------------------------------------------------------
    # Rendu texte
    # ------------------------------------------------------------------
    def _lignes_texte(self, groupes, date_debut, date_fin):
        lignes = [
            f"Stock dormant par superviseur — période du "
            f"{date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
            "",
        ]
        for index, groupe in enumerate(groupes):
            if index > 0:
                lignes.append(SEPARATEUR)

            superviseur = groupe["superviseur"]
            lignes.append(superviseur.full_name if superviseur else "Sans superviseur")

            agents = sorted(
                groupe["agents"].values(),
                key=lambda bloc: bloc["agent"].full_name.lower(),
            )
            for bloc in agents:
                lignes.append(bloc["agent"].full_name)
                for ligne in bloc["lignes"]:
                    lignes.append(
                        f"  - {ligne['produit']} reçu le {_date_fr(ligne['date_reception'])} "
                        f"(reste {ligne['quantite_restante']})"
                    )
        return lignes

    # ------------------------------------------------------------------
    # Rendu PDF (reportlab, même stack que direction/exports)
    # ------------------------------------------------------------------
    def _generer_pdf(self, groupes, date_debut, date_fin, output):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

        if not output:
            dossier = chemin_rapport("rapports", date_debut)
            output = os.path.join(
                dossier, f"stock_dormant_{date_debut}_{date_fin}.pdf"
            )
        os.makedirs(os.path.dirname(output), exist_ok=True)

        styles = getSampleStyleSheet()
        style_superviseur = ParagraphStyle(
            "superviseur", parent=styles["Heading2"], spaceBefore=10, spaceAfter=4
        )
        style_agent = ParagraphStyle(
            "agent", parent=styles["Heading4"], leftIndent=12, spaceBefore=6, spaceAfter=2
        )
        style_produit = ParagraphStyle(
            "produit", parent=styles["Normal"], leftIndent=28, fontSize=9, leading=13
        )

        elements = [
            Paragraph("<b>STOCK DORMANT PAR SUPERVISEUR</b>", styles["Title"]),
            Paragraph(
                f"Produits reçus du {date_debut.strftime('%d/%m/%Y')} "
                f"au {date_fin.strftime('%d/%m/%Y')}, encore détenus par les agents.<br/>"
                f"Généré le {timezone.localdate().strftime('%d/%m/%Y')}",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        for index, groupe in enumerate(groupes):
            if index > 0:
                elements.append(Spacer(1, 6))
                elements.append(HRFlowable(width="100%"))

            superviseur = groupe["superviseur"]
            nom_sup = superviseur.full_name if superviseur else "Sans superviseur"
            elements.append(Paragraph(f"<b>{nom_sup}</b>", style_superviseur))

            agents = sorted(
                groupe["agents"].values(),
                key=lambda bloc: bloc["agent"].full_name.lower(),
            )
            for bloc in agents:
                elements.append(Paragraph(bloc["agent"].full_name, style_agent))
                for ligne in bloc["lignes"]:
                    elements.append(Paragraph(
                        f"- {ligne['produit']} reçu le {_date_fr(ligne['date_reception'])} "
                        f"(reste {ligne['quantite_restante']})",
                        style_produit,
                    ))

        SimpleDocTemplate(
            output, pagesize=A4,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36,
        ).build(elements)

        return output
