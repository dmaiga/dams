# services/vente_export.py
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


class VenteExportService:

    # -------------------------------------------------------------------
    @staticmethod
    def export_excel(ventes_queryset, date_debut, date_fin):
        """Retourne un fichier Excel (BytesIO) pour téléchargement"""

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ventes"

        # En-tête
        headers = [
            "Date vente", "Agent", "Client", "Produit",
            "Qté", "Prix unitaire", "Montant total", "Type"
        ]
        ws.append(headers)

        for col in range(1, len(headers) + 1):
            ws.cell(row=1, column=col).font = Font(bold=True)

        # Contenu
        for v in ventes_queryset:
            ws.append([
                v.date_vente.strftime("%Y-%m-%d %H:%M"),
                v.agent.full_name,
                v.nom_client,
                v.produit_nom,
                float(v.quantite),
                float(v.prix_vente_unitaire),
                float(v.total_vente),
                v.get_type_vente_display(),
            ])

        # Ajustements des colonnes
        for column_cells in ws.columns:
            length = max(len(str(cell.value)) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = length + 2

        # Sauvegarde
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    # -------------------------------------------------------------------
    @staticmethod
    def export_pdf(ventes_queryset, date_debut, date_fin):
        """Retourne un fichier PDF (BytesIO)"""

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            title="Liste des ventes"
        )

        styles = getSampleStyleSheet()
        elements = []

        # Titre
        titre = Paragraph(
            f"<b>Liste des ventes du {date_debut.date()} au {date_fin.date()}</b>",
            styles["Title"]
        )
        elements.append(titre)

        # Tableau PDF
        data = [
            ["Date vente", "Agent", "Client", "Produit", "Qté",
             "PU", "Montant", "Type"]
        ]

        for v in ventes_queryset:
            data.append([
                v.date_vente.strftime("%Y-%m-%d %H:%M"),
                v.agent.full_name,
                v.nom_client,
                v.produit_nom,
                float(v.quantite),
                float(v.prix_vente_unitaire),
                float(v.total_vente),
                v.get_type_vente_display(),
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        return buffer
