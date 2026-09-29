# services/superviseur_ventes_fournisseur_export.py
from io import BytesIO

import openpyxl
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HEADERS = [
    "Fournisseur", "Produit", "Prix d'achat unitaire", "Quantité reçue", "Prix total (lot)",
    "Date réception", "Vendeur", "Date vente", "Quantité vendue", "Quantité perdue",
    "Prix de vente", "Montant",
]


def _nom_vendeur(vente):
    return vente.agent.full_name if vente.agent else "—"


def _fcfa(valeur):
    """Format FCFA avec séparateur de milliers en espace (convention française), sans décimales
    — les prix/quantités reçus ne portent pas de centimes dans ce métier."""
    return f"{valeur:,.0f}".replace(",", " ")


def _quantite_perdue(vente):
    """Quantité déclarée perdue par le superviseur au moment de la vente (Perte.vente, produit
    vrac) — nécessaire au rapprochement fournisseur/lot/vente/perte (correction 29/09/2026,
    demande mdmaiga). Un produit conditionné n'a qu'un commentaire de perte, pas de quantité
    (cf. Vente.commentaire_perte) : on l'affiche en repli quand aucune Perte chiffrée n'existe."""
    total = sum((p.quantite_perdue or 0) for p in vente.pertes_liees.all())
    if total:
        return f"{float(total):.2f}"
    return vente.commentaire_perte or "—"


def _ligne(nom_fournisseur, bloc_produit, vente):
    return [
        nom_fournisseur,
        bloc_produit["produit"].nom,
        float(bloc_produit["prix_achat"]),
        float(bloc_produit["quantite_recue"]),
        float(bloc_produit["prix_total"]),
        bloc_produit["date_reception"].strftime("%d/%m/%Y"),
        _nom_vendeur(vente),
        vente.date_vente.strftime("%d/%m/%Y %H:%M"),
        float(vente.quantite),
        _quantite_perdue(vente),
        float(vente.prix_vente_unitaire),
        float(vente.quantite * vente.prix_vente_unitaire),
    ]


class SuperviseurVentesFournisseurExportService:
    """Export des ventes du superviseur et de ses agents, organisé par fournisseur puis par
    lot reçu (produit, prix d'achat, quantité reçue, prix total, date de réception) — retrace un
    produit de sa réception jusqu'à sa vente (demande mdmaiga, 24/09/2026). `groupes` vient de
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

        largeurs = (22, 22, 18, 14, 16, 16, 22, 18, 14, 14, 14, 14)
        for col, largeur in zip("ABCDEFGHIJKL", largeurs):
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
                # Un champ par ligne (correction 29/09/2026, demande mdmaiga) : la quantité
                # reçue et le prix total du lot sont plus lisibles séparés du prix unitaire
                # qu'inline sur une seule phrase.
                elements.append(Paragraph(bloc_produit["produit"].nom, styles["Heading3"]))
                elements.append(Paragraph(
                    f"Prix d'achat unitaire : {_fcfa(bloc_produit['prix_achat'])} FCFA<br/>"
                    f"Quantité reçue : {bloc_produit['quantite_recue']:.2f}<br/>"
                    f"Prix total : {_fcfa(bloc_produit['prix_total'])} FCFA<br/>"
                    f"Reçu le : {bloc_produit['date_reception']:%d/%m/%Y}",
                    styles["Normal"],
                ))
                elements.append(Spacer(1, 6))

                data = [["Vendeur", "Date vente", "Qté vendue", "Qté perdue", "Prix de vente", "Montant"]]
                for vente in bloc_produit["ventes"]:
                    data.append([
                        _nom_vendeur(vente),
                        vente.date_vente.strftime("%d/%m/%Y %H:%M"),
                        f"{vente.quantite:.2f}",
                        _quantite_perdue(vente),
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
