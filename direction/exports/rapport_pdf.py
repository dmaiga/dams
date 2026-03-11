from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from collections import defaultdict
from datetime import date

from utils.rapport_utils import jours_non_travailles_individuels
from reportlab.lib.enums import TA_CENTER


# ===============================
# Date lisible FR
# ===============================
def format_date_courte_fr(d):
    jours = [
        "Lundi", "Mardi", "Mercredi",
        "Jeudi", "Vendredi", "Samedi", "Dimanche"
    ]
    return f"{jours[d.weekday()]} {d.strftime('%d/%m/%Y')}"


# ===============================
# GENERATION PDF
# ===============================
def generer_rapport_ventes_pdf(
    rapport,
    agents_sans_vente,
    date_debut,
    date_fin,
    fichier
):

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
        alignment=2,
    )

    # ===============================
    # ENTETE
    # ===============================
    elements.append(Paragraph("<b>RAPPORT DES VENTES</b>", styles["Title"]))

    elements.append(Paragraph(
        f"Période : du {format_date_courte_fr(date_debut)} "
        f"au {format_date_courte_fr(date_fin)}<br/>"
        f"Généré le : {format_date_courte_fr(date.today())}",
        styles["Normal"]
    ))

    elements.append(Spacer(1, 12))

    # ===============================
    # REGROUPEMENT PAR AGENT
    # ===============================
    from core.models import Agent

    agents = defaultdict(list)
    agents_objs = {}

    for row in rapport:
        agent_id = row["agent__id"]

        if agent_id not in agents_objs:
            agents_objs[agent_id] = Agent.objects.get(id=agent_id)

        agents[agent_id].append(row)
    # ===============================
    # PAR AGENT
    # ===============================
    for agent_id, ventes in agents.items():

        agent_obj = agents_objs[agent_id]
        agent_nom = f"{agent_obj.user.first_name} {agent_obj.user.last_name}"
        # 🔥 total période agent
        total_agent_kg = sum(float(v["total_kg"]) for v in ventes)

        if agent_obj.est_en_test:
            titre = (
                f"Agent : {agent_nom} "
                f"(EN TEST - {agent_obj.jours_restants_test} jours restants) "
                f"— Total période : {total_agent_kg:.2f} kg"
            )
        else:
            titre = f"Agent : {agent_nom} — Total période : {total_agent_kg:.2f} kg"
        
        elements.append(
            Paragraph(f"<b>{titre}</b>", styles["Heading2"])
        )

        elements.append(Spacer(1, 6))

        data = [[
            Paragraph("<b>Produit</b>", styles["Normal"]),
            Paragraph("<b>Quantité</b>", styles["Normal"]),
            Paragraph("<b>Poids (kg)</b>", styles["Normal"]),
        ]]

        col_widths = [260, 80, 80]

        jours_vendus = set()
        dernier_jour = None
        totaux_par_jour = defaultdict(float)

        # ===============================
        # LIGNES VENTES
        # ===============================
        for v in ventes:

            jour = v["date_vente__date"]
            kg = float(v["total_kg"])

            jours_vendus.add(jour)
            totaux_par_jour[jour] += kg

            # afficher date une seule fois
            if jour != dernier_jour:
                data.append([
                    Paragraph(format_date_courte_fr(jour), style_date),
                    "", ""
                ])
                dernier_jour = jour

            data.append([
                Paragraph(
                    v["detail_distribution__lot__produit__nom"],
                    style_produit
                ),
                Paragraph(str(v["total_quantite"]), style_num),
                Paragraph(f"{kg:.2f}", style_num),
            ])

        table = Table(data, colWidths=col_widths, repeatRows=1)

        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("SPAN", (0, 1), (-1, 1)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 10))

        # ===============================
        # TOTAL PAR JOUR
        # ===============================
        elements.append(
            Paragraph("<b>Total vendu par jour</b>", styles["Heading3"])
        )

        for jour, total in sorted(totaux_par_jour.items()):
            elements.append(
                Paragraph(
                    f"{format_date_courte_fr(jour)} : {total:.2f} kg",
                    styles["Normal"]
                )
            )

        # ===============================
        # JOURS SANS ACTIVITE
        # ===============================
        jours_absents = jours_non_travailles_individuels(
            date_debut,
            date_fin,
            jours_vendus
        )

        elements.append(
            Paragraph("<b>Jours sans activité</b>", styles["Heading3"])
        )

        if jours_absents:
            for j in jours_absents:
                elements.append(Paragraph(f"- {j}", styles["Normal"]))
        else:
            elements.append(
                Paragraph(
                    "Aucun jour ouvré sans activité sur la période.",
                    styles["Normal"]
                )
            )

        elements.append(Spacer(1, 15))

    # ===============================
    # AGENTS SANS VENTE
    # ===============================
    elements.append(
        Paragraph(
            "<b>Agents actifs sans vente sur la période</b>",
            styles["Heading2"]
        )
    )

 
    agents_test = []
    agents_confirmes = []

    for agent in agents_sans_vente:
        if agent.est_en_test:
            agents_test.append(agent)
        else:
            agents_confirmes.append(agent)

    if agents_test:
        elements.append(
            Paragraph("<b>Agents en période d'essai sans vente</b>", styles["Heading3"])
        )
    
        for agent in agents_test:
            nom = f"{agent.user.first_name} {agent.user.last_name}"
            texte = f"- {nom} ({agent.jours_restants_test} jours restants)"
            elements.append(Paragraph(texte, styles["Normal"]))
    
    if agents_confirmes:
        elements.append(
            Paragraph("<b>Agents confirmés sans vente</b>", styles["Heading3"])
        )

        for agent in agents_confirmes:
            nom = f"{agent.user.first_name} {agent.user.last_name}"
            elements.append(Paragraph(f"- {nom}", styles["Normal"]))
    # ===============================
    # BUILD PDF
    # ===============================
    doc.build(elements)
