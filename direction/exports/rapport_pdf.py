from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from collections import defaultdict
from datetime import date

from utils.rapport_utils import (
    format_date_fr,
    jours_non_travailles_individuels
)


def generer_rapport_ventes_pdf(rapport, date_debut, date_fin, fichier):
    doc = SimpleDocTemplate(fichier, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>RAPPORT DES VENTES</b>", styles["Title"]))
    elements.append(Paragraph(
        f"Période : du {format_date_fr(date_debut)} au {format_date_fr(date_fin)}<br/>"
        f"Généré le : {format_date_fr(date.today())}",
        styles["Normal"]
    ))

    agents = defaultdict(list)

    for row in rapport:
        agent = f"{row['agent__user__first_name']} {row['agent__user__last_name']}"
        agents[agent].append(row)

    for agent, ventes in agents.items():
        elements.append(Paragraph(f"<b>Agent : {agent}</b>", styles["Heading2"]))

        data = [["Date", "Produit", "Quantité"]]
        jours_vendus = set()

        for v in ventes:
            jours_vendus.add(v["date_vente__date"])
            data.append([
                format_date_fr(v["date_vente__date"]),
                v["detail_distribution__lot__produit__nom"],
                str(v["total_quantite"]),
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)

        jours_absents = jours_non_travailles_individuels(
            date_debut, date_fin, jours_vendus
        )

        elements.append(Paragraph(
            "<b>Jours sans activité</b>",
            styles["Heading3"]
        ))

        if jours_absents:
            for j in jours_absents:
                elements.append(Paragraph(f"- {j}", styles["Normal"]))
        else:
            elements.append(Paragraph(
                "Aucun jour ouvré sans activité sur la période.",
                styles["Normal"]
            ))

    doc.build(elements)
