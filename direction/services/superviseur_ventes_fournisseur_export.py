# services/superviseur_ventes_fournisseur_export.py
from io import BytesIO

import openpyxl
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HEADERS = [
    "Fournisseur", "Produit", "Prix d'achat", "Date réception",
    "Vendeur", "Date vente", "Quantité", "Prix de vente", "Montant",
]


def _nom_vendeur(vente):
    return vente.agent.full_name if vente.agent else "—"


def _ligne(nom_fournisseur, bloc_produit, vente):
    return [
        nom_fournisseur,
        bloc_produit["produit"].nom,
        float(bloc_produit["prix_achat"]),
        bloc_produit["date_reception"].strftime("%d/%m/%Y"),
        _nom_vendeur(vente),
        vente.date_vente.strftime("%d/%m/%Y %H:%M"),
        float(vente.quantite),
        float(vente.prix_vente_unitaire),
        float(vente.quantite * vente.prix_vente_unitaire),
    ]


class SuperviseurVentesFournisseurExportService:
    """Export des ventes du superviseur et de ses agents, organisé par fournisseur puis par
    lot reçu (produit, prix d'achat, date de réception) — retrace un produit de sa réception
    jusqu'à sa vente (demande mdmaiga, 24/09/2026). `groupes` vient de
    SuperviseurAgentsService.ventes_par_fournisseur."""

    @staticmethod
    def export_excel(groupes):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ventes par fournisseur"

        ws.append(HEADERS)
        for col in range(1, len(HEADERS) + 1):
            ws.cell(row=1, column=col).font = Font(bold=True)

        for groupe in groupes:
            nom_fournisseur = groupe["fournisseur"].nom if groupe["fournisseur"] else "Sans fournisseur"
            for bloc_produit in groupe["produits"]:
                for vente in bloc_produit["ventes"]:
                    ws.append(_ligne(nom_fournisseur, bloc_produit, vente))

        largeurs = (22, 22, 14, 16, 22, 18, 12, 14, 14)
        for col, largeur in zip("ABCDEFGHI", largeurs):
            ws.column_dimensions[col].width = largeur

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def export_pdf(superviseur, date_debut, date_fin, groupes):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            title=f"Ventes par fournisseur — {superviseur.full_name}",
        )

        styles = getSampleStyleSheet()
        elements = [
            Paragraph(
                f"<b>{superviseur.full_name}</b> — ventes par fournisseur (superviseur et agents)",
                styles["Title"],
            ),
            Paragraph(f"Période : {date_debut:%d/%m/%Y} → {date_fin:%d/%m/%Y}", styles["Normal"]),
            Spacer(1, 12),
        ]

        for groupe in groupes:
            nom_fournisseur = groupe["fournisseur"].nom if groupe["fournisseur"] else "Sans fournisseur"
            elements.append(Paragraph(f"<b>{nom_fournisseur}</b>", styles["Heading2"]))

            for bloc_produit in groupe["produits"]:
                elements.append(Paragraph(
                    f"{bloc_produit['produit'].nom} — prix d'achat "
                    f"{bloc_produit['prix_achat']:.0f} FCFA — reçu le "
                    f"{bloc_produit['date_reception']:%d/%m/%Y}",
                    styles["Heading3"],
                ))

                data = [["Vendeur", "Date vente", "Quantité", "Prix de vente", "Montant"]]
                for vente in bloc_produit["ventes"]:
                    data.append([
                        _nom_vendeur(vente),
                        vente.date_vente.strftime("%d/%m/%Y %H:%M"),
                        f"{vente.quantite:.2f}",
                        f"{vente.prix_vente_unitaire:.0f}",
                        f"{vente.quantite * vente.prix_vente_unitaire:.0f}",
                    ])

                table = Table(data, repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 10))

            elements.append(Spacer(1, 14))

        doc.build(elements)
        buffer.seek(0)
        return buffer
