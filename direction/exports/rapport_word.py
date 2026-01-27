from collections import defaultdict
from datetime import date
from docx import Document

from utils.rapport_utils import (
    format_date_fr,
    jours_non_travailles_individuels
)


def generer_rapport_ventes_word(rapport, date_debut, date_fin, fichier):
    document = Document()

    document.add_heading("RAPPORT DES VENTES", level=1)

    document.add_paragraph(
        f"Période : du {format_date_fr(date_debut)} au {format_date_fr(date_fin)}\n"
        f"Généré le : {format_date_fr(date.today())}"
    )

    agents = defaultdict(list)

    for row in rapport:
        agent = f"{row['agent__user__first_name']} {row['agent__user__last_name']}"
        agents[agent].append(row)

    for agent, ventes in agents.items():
        document.add_heading(f"Agent : {agent}", level=2)

        table = document.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        hdr[0].text = "Date"
        hdr[1].text = "Produit"
        hdr[2].text = "Quantité"

        jours_vendus = set()

        for v in ventes:
            jours_vendus.add(v["date_vente__date"])
            r = table.add_row().cells
            r[0].text = format_date_fr(v["date_vente__date"])
            r[1].text = v["detail_distribution__lot__produit__nom"]
            r[2].text = str(v["total_quantite"])

        # 🔍 JOURS NON TRAVAILLÉS – INDIVIDUEL
        jours_absents = jours_non_travailles_individuels(
            date_debut, date_fin, jours_vendus
        )

        document.add_paragraph("Jours sans activité :")

        if jours_absents:
            document.add_paragraph("Jours sans activité sur la période :")
            for j in jours_absents:
                document.add_paragraph(f"- {j}", style="List Bullet")
        else:
            document.add_paragraph(
                "Aucun jour ouvré sans activité sur la période."
            )

    document.save(fichier)
