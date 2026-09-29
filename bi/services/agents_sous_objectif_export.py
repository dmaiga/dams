# services/agents_sous_objectif_export.py
from io import BytesIO

import openpyxl
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from bi.constants import SEUIL_KG_JOUR_FAIBLE

HEADERS_FIXES = ["Agent", "Date de début", "Ancienneté"]


def _valeur_kg_jour(kg_par_jour):
    if kg_par_jour is None:
        return "—"
    return round(float(kg_par_jour), 2)


def _ligne(agent):
    return [
        agent["nom_complet"],
        agent["date_debut"].strftime("%d/%m/%Y") if agent["date_debut"] else "—",
        agent["anciennete_libelle"],
    ] + [_valeur_kg_jour(col["kg_par_jour"]) for col in agent["colonnes_mois"]]


class AgentsSousObjectifExportService:
    """Export des agents sous-performants sur le mois en cours (< SEUIL_KG_JOUR_FAIBLE kg/jour),
    regroupés par superviseur, avec une colonne kg/jour par mois sur les NB_MOIS_SOUS_PERFORMANCE
    derniers mois pour voir l'évolution plutôt qu'une seule moyenne (correction 30/09/2026,
    demande mdmaiga). `groupes` et `libelles_mois` viennent de
    bi.views._agents_sous_performants_par_superviseur — libelles_mois est déjà dans l'ordre du
    plus ancien au plus récent (mois en cours en dernier), même ordre que
    agent["colonnes_mois"]. "—" = agent pas encore embauché ce mois-là (à distinguer de 0 kg/j,
    une vraie sous-performance)."""

    @staticmethod
    def export_excel(groupes, libelles_mois):
        headers = HEADERS_FIXES + [f"{libelle} (kg/j)" for libelle in libelles_mois]

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Agents sous seuil"

        for groupe in groupes:
            ws.append([f"Superviseur : {groupe['superviseur_nom']}"])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

            ws.append(headers)
            for col in range(1, len(headers) + 1):
                ws.cell(row=ws.max_row, column=col).font = Font(bold=True)

            for agent in groupe["agents"]:
                ws.append(_ligne(agent))
                for col in range(len(HEADERS_FIXES) + 1, len(headers) + 1):
                    cellule = ws.cell(row=ws.max_row, column=col)
                    if isinstance(cellule.value, (int, float)):
                        cellule.number_format = "0.00"

            ws.append([])

        largeurs = [28, 16, 22] + [16] * len(libelles_mois)
        for col, largeur in zip(ws.columns, largeurs):
            ws.column_dimensions[col[0].column_letter].width = largeur

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def export_pdf(groupes, libelles_mois):
        headers = HEADERS_FIXES + [f"{libelle} (kg/j)" for libelle in libelles_mois]

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            title="Agents sous-performants",
        )

        styles = getSampleStyleSheet()
        mois_courant_libelle = libelles_mois[-1] if libelles_mois else ""
        elements = [
            Paragraph("<b>Agents sous-performants</b>", styles["Title"]),
            Paragraph(
                f"Agents dont la moyenne de vente sur {mois_courant_libelle} (mois en cours) est "
                f"inférieure à {SEUIL_KG_JOUR_FAIBLE} kg/jour, avec la tendance des mois "
                f"précédents. Objectif individuel de référence : 50 kg/jour.",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        for groupe in groupes:
            elements.append(Paragraph(f"<b>{groupe['superviseur_nom']}</b>", styles["Heading2"]))

            data = [headers] + [_ligne(agent) for agent in groupe["agents"]]
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
