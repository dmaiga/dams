# services/stock_investigation_export.py
from io import BytesIO

import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer

from core.pdf_compact import nouveau_document, styles_compacts, tableau
from direction.constants import SEUIL_ATTENTION_JOURS
from direction.services.stock_investigation_service import StockInvestigationService
from direction.templatetags.direction_filters import format_number

HEADERS = [
    "Agent", "Produit", "Quantité", "Montant total achat", "Date de réception", "Nombre de jours",
]


def _lignes_agent(bloc_agent):
    """Une ligne par produit ; le nom de l'agent n'apparaît que sur la première
    (cellule vide ensuite) — consigne mdmaiga 02/10/2026."""
    lignes = []
    for i, p in enumerate(bloc_agent["produits"]):
        lignes.append([
            bloc_agent["agent"].full_name if i == 0 else "",
            p["produit_nom"],
            format_number(p["quantite"]),
            f"{format_number(p['montant_achat'])} FCFA",
            f"{p['date_reception']:%d/%m/%Y}",
            f"{p['jours_reception']} j",
        ])
    return lignes


class StockInvestigationExportService:
    """Export de la liste « Produits à investiguer » (sprint-14, révision
    02/10/2026) — regroupé par superviseur puis agent, une ligne par produit
    avec valorisation à l'achat, format à remettre à un agent de vérification."""

    @staticmethod
    def _groupes(lignes_annotees):
        return StockInvestigationService.regrouper_par_superviseur(lignes_annotees)

    @staticmethod
    def export_excel(lignes_annotees):
        groupes = StockInvestigationExportService._groupes(lignes_annotees)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Produits à investiguer"

        ws.append(HEADERS)
        for col in range(1, len(HEADERS) + 1):
            ws.cell(row=1, column=col).font = Font(bold=True)

        for groupe in groupes:
            nom_superviseur = groupe["superviseur"].full_name if groupe["superviseur"] else "—"
            ws.append([f"Superviseur : {nom_superviseur}"])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
            for bloc_agent in groupe["agents"]:
                for i, ligne in enumerate(_lignes_agent(bloc_agent)):
                    ws.append(ligne)
                    for col in range(1, len(HEADERS) + 1):
                        cell = ws.cell(row=ws.max_row, column=col)
                        if col in (3, 4, 6):
                            cell.alignment = Alignment(horizontal="right")
                        # Trait épais au-dessus du premier produit de chaque agent :
                        # sépare nettement les agents (retour mdmaiga 02/10/2026).
                        if i == 0:
                            cell.border = Border(top=Side(style="medium"))

        for lettre, largeur in zip("ABCDEF", (24, 24, 12, 22, 18, 16)):
            ws.column_dimensions[lettre].width = largeur

        # Mise en page d'impression : A4 portrait, une page de large, en-tête répété.
        ws.page_setup.orientation = "portrait"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = "1:1"
        ws.page_margins.left = ws.page_margins.right = 0.4

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def export_pdf(lignes_annotees):
        groupes = StockInvestigationExportService._groupes(lignes_annotees)

        buffer = BytesIO()
        doc = nouveau_document(buffer, "Produits à investiguer")

        styles = styles_compacts()
        elements = [
            Paragraph(
                "<b>Produits à investiguer — checklist terrain</b>", styles["Title"]
            ),
            Paragraph(
                f"Produits en circulation depuis plus de {SEUIL_ATTENTION_JOURS} jours sans vente enregistrée.",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        for groupe in groupes:
            nom_superviseur = groupe["superviseur"].full_name if groupe["superviseur"] else "—"
            elements.append(Paragraph(f"<b>Superviseur : {nom_superviseur}</b>", styles["Heading3"]))

            data = [HEADERS]
            # Colonnes numériques alignées à droite.
            extra = [("ALIGN", (2, 1), (3, -1), "RIGHT"), ("ALIGN", (5, 1), (5, -1), "RIGHT")]
            # Un fond par agent (alternance blanc / gris par bloc agent, pas par ligne) et
            # un trait épais entre deux agents : évite de confondre leurs produits.
            for n, bloc_agent in enumerate(groupe["agents"]):
                debut = len(data)
                data.extend(_lignes_agent(bloc_agent))
                fin = len(data) - 1
                fond = colors.white if n % 2 == 0 else colors.HexColor("#E3ECF5")
                extra.append(("BACKGROUND", (0, debut), (-1, fin), fond))
                if n > 0:
                    extra.append(("LINEABOVE", (0, debut), (-1, debut), 1.5, colors.black))
            elements.append(tableau(data, doc, fractions=[3, 3, 1.5, 2.5, 2, 1.5], extra_style=extra))
            elements.append(Spacer(1, 8))

        doc.build(elements)

        buffer.seek(0)
        return buffer
