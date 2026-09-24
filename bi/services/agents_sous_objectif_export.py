# services/agents_sous_objectif_export.py
from io import BytesIO

import openpyxl
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from bi.constants import SEUIL_KG_JOUR_FAIBLE

HEADERS = ["Agent", "Superviseur", "Jours actifs", "Kg vendus", "Kg/jour", "Date début", "Ancienneté (j)"]


def _ligne(a):
    return [
        a.nom_complet,
        a.superviseur_nom or "—",
        a.jours_label,
        float(a.kg_vendus or 0),
        float(a.kg_par_jour or 0),
        a.date_debut_fonction_export.strftime("%d/%m/%Y") if a.date_debut_fonction_export else "—",
        a.anciennete_jours if a.anciennete_jours is not None else "—",
    ]


class AgentsSousObjectifExportService:
    """Export des agents dont la moyenne de vente est en dessous du seuil
    SEUIL_KG_JOUR_FAIBLE (dashboard bi:agents, demande mdmaiga 24/09/2026) —
    même liste que celle affichée à l'écran (filtres période/superviseur/type
    déjà appliqués en amont par la vue)."""

    @staticmethod
    def export_excel(agents):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Agents sous seuil"

        ws.append(HEADERS)
        for col in range(1, len(HEADERS) + 1):
            ws.cell(row=1, column=col).font = Font(bold=True)

        for a in agents:
            ws.append(_ligne(a))

        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 14
        ws.column_dimensions["D"].width = 14
        ws.column_dimensions["E"].width = 12
        ws.column_dimensions["F"].width = 14
        ws.column_dimensions["G"].width = 16

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def export_pdf(agents):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            title="Agents sous le seuil",
        )

        styles = getSampleStyleSheet()
        elements = [
            Paragraph("<b>Agents en dessous de la moyenne de vente</b>", styles["Title"]),
            Paragraph(
                f"Agents dont la moyenne de vente est inférieure à {SEUIL_KG_JOUR_FAIBLE} kg/jour "
                "sur la période sélectionnée.",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        data = [HEADERS] + [_ligne(a) for a in agents]
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

        doc.build(elements)
        buffer.seek(0)
        return buffer
