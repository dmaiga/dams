# services/agents_sous_objectif_export.py
from io import BytesIO

import openpyxl
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from bi.constants import SEUIL_KG_JOUR_FAIBLE

HEADERS = ["Agent", "Date de début", "Ancienneté", "Kg/jour"]


def _ligne(agent):
    return [
        agent["nom_complet"],
        agent["date_debut"].strftime("%d/%m/%Y") if agent["date_debut"] else "—",
        agent["anciennete_libelle"],
        round(float(agent["kg_par_jour"]), 2),
    ]


class AgentsSousObjectifExportService:
    """Export des agents sous-performants (moyenne < SEUIL_KG_JOUR_FAIBLE kg/jour sur la
    période sélectionnée), regroupés par superviseur (correction 29/09/2026, demande mdmaiga) —
    `groupes` vient de bi.views._agents_sous_performants_par_superviseur, déjà trié par
    superviseur puis par kg/jour croissant à l'intérieur de chaque groupe."""

    @staticmethod
    def export_excel(groupes, date_debut, date_fin):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Agents sous seuil"

        for groupe in groupes:
            ws.append([f"Superviseur : {groupe['superviseur_nom']}"])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

            ws.append(HEADERS)
            for col in range(1, len(HEADERS) + 1):
                ws.cell(row=ws.max_row, column=col).font = Font(bold=True)

            for agent in groupe["agents"]:
                ws.append(_ligne(agent))
                ws.cell(row=ws.max_row, column=len(HEADERS)).number_format = "0.00"

            ws.append([])

        largeurs = (28, 16, 22, 12)
        for col, largeur in zip("ABCD", largeurs):
            ws.column_dimensions[col].width = largeur

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def export_pdf(groupes, date_debut, date_fin):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            title="Agents sous-performants",
        )

        styles = getSampleStyleSheet()
        elements = [
            Paragraph("<b>Agents sous-performants</b>", styles["Title"]),
            Paragraph(
                f"Agents dont la moyenne de vente est inférieure à {SEUIL_KG_JOUR_FAIBLE} kg/jour "
                f"sur la période du {date_debut:%d/%m/%Y} au {date_fin:%d/%m/%Y}.",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        for groupe in groupes:
            elements.append(Paragraph(f"<b>{groupe['superviseur_nom']}</b>", styles["Heading2"]))

            data = [HEADERS] + [_ligne(agent) for agent in groupe["agents"]]
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 14))

        doc.build(elements)
        buffer.seek(0)
        return buffer
