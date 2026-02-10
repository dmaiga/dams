from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from collections import defaultdict
from datetime import date

from utils.rapport_utils import (
    jours_non_travailles_individuels
)
from reportlab.lib.enums import TA_CENTER



# ✅ Date courte lisible
def format_date_courte_fr(d):
    jours = [
        "Lundi", "Mardi", "Mercredi",
        "Jeudi", "Vendredi", "Samedi", "Dimanche"
    ]
    jour_nom = jours[d.weekday()]
    return f"{jour_nom} {d.strftime('%d/%m/%Y')}"


def generer_rapport_ventes_pdf(rapport, date_debut, date_fin, fichier):
    doc = SimpleDocTemplate(
        fichier,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ===============================
    # Styles
    # ===============================
    style_date = ParagraphStyle(
        "date",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        alignment=TA_CENTER,  
        spaceBefore=6,
        spaceAfter=6,
    )

    style_produit = ParagraphStyle(
        "produit",
        parent=styles["Normal"],
        fontSize=9,
        leftIndent=6,
        wordWrap="CJK",
    )

    style_num = ParagraphStyle(
        "num",
        parent=styles["Normal"],
        fontSize=9,
        alignment=2,  # right
    )

    # ===============================
    # En-tête
    # ===============================
    elements.append(Paragraph("<b>RAPPORT DES VENTES</b>", styles["Title"]))
    elements.append(Paragraph(
        f"Période : du {format_date_courte_fr(date_debut)} "
        f"au {format_date_courte_fr(date_fin)}<br/>"
        f"Généré le : {format_date_courte_fr(date.today())}",
        styles["Normal"]
    ))

    # ===============================
    # Regroupement par agent
    # ===============================
    agents = defaultdict(list)
    for row in rapport:
        agent = f"{row['agent__user__first_name']} {row['agent__user__last_name']}"
        agents[agent].append(row)

    # ===============================
    # Par agent
    # ===============================
    for agent, ventes in agents.items():
        elements.append(Paragraph(f"<b>Agent : {agent}</b>", styles["Heading2"]))

        data = [[
            Paragraph("<b>Produit</b>", styles["Normal"]),
            Paragraph("<b>Quantité</b>", styles["Normal"]),
            Paragraph("<b>Poids (kg)</b>", styles["Normal"]),
        ]]

        col_widths = [260, 80, 80]
        jours_vendus = set()
        dernier_jour = None

        for v in ventes:
            jour = v["date_vente__date"]
            jours_vendus.add(jour)

            # 🔹 Afficher la date UNE SEULE FOIS
            if jour != dernier_jour:
                data.append([
                    Paragraph(format_date_courte_fr(jour), style_date),
                    "", ""
                ])
                dernier_jour = jour

            data.append([
                Paragraph(v["detail_distribution__lot__produit__nom"], style_produit),
                Paragraph(str(v["total_quantite"]), style_num),
                Paragraph(f"{v['total_kg']:.2f}", style_num),
            ])

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("SPAN", (0, 1), (-1, 1)),  # date en pleine largeur
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(table)

        # ===============================
        # Jours sans activité
        # ===============================
        jours_absents = jours_non_travailles_individuels(
            date_debut, date_fin, jours_vendus
        )

        elements.append(Paragraph("<b>Jours sans activité</b>", styles["Heading3"]))

        if jours_absents:
            for j in jours_absents:
                elements.append(Paragraph(f"- {j}", styles["Normal"]))
        else:
            elements.append(Paragraph(
                "Aucun jour ouvré sans activité sur la période.",
                styles["Normal"]
            ))

    doc.build(elements)
