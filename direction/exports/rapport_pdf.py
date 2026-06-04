# rapport_pdf.py
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
    # REGROUPEMENT PAR SUPERVISEUR
    # ===============================
    from core.models import Agent

    superviseurs = defaultdict(
        lambda: {
            "superviseur": None,
            "agents": defaultdict(list)
        }
    )

    agents_cache = {}

    for row in rapport:

        agent_id = row["agent__id"]

        if agent_id not in agents_cache:

            agents_cache[agent_id] = (
                Agent.objects
                .select_related(
                    "user",
                    "superviseur__user"
                )
                .get(id=agent_id)
            )

        agent = agents_cache[agent_id]

        # Exclusion ventes gros
        if agent.type_agent == "agent_gros":
            continue

        superviseur = agent.superviseur

        # ====================================
        # CAS 1 : AGENT SANS SUPERVISEUR
        # ====================================
        if not superviseur:

            superviseurs["sans_superviseur"]["superviseur"] = None

            superviseurs[
                "sans_superviseur"
            ]["agents"][
                agent.id
            ].append(row)

            continue

        # ====================================
        # CAS 2 : JEAN CLAUDE EXCLU
        # ====================================
        if superviseur.user.username == "jeanclaude.sup":
            continue

        # ====================================
        # CAS 3 : SUPERVISEUR INACTIF
        # ====================================
        if not superviseur.est_actif:
            continue

        # ====================================
        # CAS 4 : SUPERVISEUR VALIDE
        # ====================================
        if superviseur.type_agent != "entrepot":
            continue

        superviseurs[
            superviseur.id
        ]["superviseur"] = superviseur

        superviseurs[
            superviseur.id
        ]["agents"][
            agent.id
        ].append(row)
   
    # ===============================
    # PAR SUPERVISEUR
    # ===============================
    for superviseur_data in superviseurs.values():

        superviseur = superviseur_data["superviseur"]
        agents = superviseur_data["agents"]

        # ----------------------------------
        # TITRE
        # ----------------------------------
        if superviseur:

            titre_superviseur = (
                f"SUPERVISEUR : "
                f"{superviseur.full_name.upper()}"
            )

        else:

            titre_superviseur = (
                "AGENTS SANS SUPERVISEUR"
            )

        # ----------------------------------
        # STATS
        # ----------------------------------
        total_equipe = 0

        for ventes in agents.values():

            total_equipe += sum(
                float(v["total_kg"])
                for v in ventes
            )

        nb_agents_vendeurs = len(agents)

        if superviseur:

            nb_agents_actifs = (
                superviseur.agents_geres
                .filter(est_actif=True)
                .exclude(type_agent="agent_gros")
                .count()
            )

            nb_agents_sans_vente = max(
                0,
                nb_agents_actifs - nb_agents_vendeurs
            )

        else:

            nb_agents_actifs = len(agents)
            nb_agents_sans_vente = 0

        elements.append(
            Paragraph(
                f"<b>{titre_superviseur}</b>",
                styles["Heading1"]
            )
        )

        elements.append(
            Paragraph(
                (
                    f"Agents actifs : {nb_agents_actifs}<br/>"
                    f"Agents ayant vendu : {nb_agents_vendeurs}<br/>"
                    f"Agents sans vente : {nb_agents_sans_vente}<br/>"
                    f"Total équipe : {total_equipe:.2f} kg"
                ),
                styles["Normal"]
            )
        )

        elements.append(
            Spacer(1, 12)
        )

        # ====================================
        # AGENTS DU SUPERVISEUR
        # ====================================
    
        for agent_id, ventes in agents.items():

            agent_obj = agents_cache[agent_id]

            agent_nom = (
                f"{agent_obj.user.first_name} "
                f"{agent_obj.user.last_name}"
            )

            total_agent_kg = sum(
                float(v["total_kg"])
                for v in ventes
            )

            if agent_obj.est_en_test:

                titre = (
                    f"Agent : {agent_nom} "
                    f"(EN TEST - "
                    f"{agent_obj.jours_restants_test} jours restants)"
                    f" — Total période : "
                    f"{total_agent_kg:.2f} kg"
                )

            else:

                titre = (
                    f"Agent : {agent_nom}"
                    f" — Total période : "
                    f"{total_agent_kg:.2f} kg"
                )

            elements.append(
                Paragraph(
                    f"<b>{titre}</b>",
                    styles["Heading2"]
                )
            )

            elements.append(
                Spacer(1, 6)
            )

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
            # VENTES
            # ===============================
            for v in ventes:
            
                jour = v["date_vente__date"]
            
                kg = float(v["total_kg"])
            
                jours_vendus.add(jour)
            
                totaux_par_jour[jour] += kg
            
                if jour != dernier_jour:
                
                    data.append([
                        Paragraph(
                            format_date_courte_fr(jour),
                            style_date
                        ),
                        "",
                        ""
                    ])
            
                    dernier_jour = jour
            
                poids_unitaire = (
                    v["detail_distribution__lot__produit__poids_unitaire_kg"]
                )
            
                if poids_unitaire:
                    quantite_affichee = str(v["total_quantite"])
                else:
                    quantite_affichee = "-"
            
                data.append([
                    Paragraph(
                        v["detail_distribution__lot__produit__nom"],
                        style_produit
                    ),
                    Paragraph(
                        quantite_affichee,
                        style_num
                    ),
                    Paragraph(
                        f"{kg:.2f}",
                        style_num
                    ),
                ])
            table = Table(
                data,
                colWidths=col_widths,
                repeatRows=1
            )

            table.setStyle(
                TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("SPAN", (0, 1), (-1, 1)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )

            elements.append(table)

            elements.append(
                Spacer(1, 10)
            )

            # ===============================
            # TOTAL PAR JOUR
            # ===============================
            elements.append(
                Paragraph(
                    "<b>Total vendu par jour</b>",
                    styles["Heading3"]
                )
            )

            for jour, total in sorted(
                totaux_par_jour.items()
            ):

                elements.append(
                    Paragraph(
                        (
                            f"{format_date_courte_fr(jour)}"
                            f" : {total:.2f} kg"
                        ),
                        styles["Normal"]
                    )
                )

            # ===============================
            # JOURS SANS ACTIVITÉ
            # ===============================
            jours_absents = (
                jours_non_travailles_individuels(
                    date_debut,
                    date_fin,
                    jours_vendus
                )
            )

            elements.append(
                Paragraph(
                    "<b>Jours sans activité</b>",
                    styles["Heading3"]
                )
            )

            if jours_absents:

                for j in jours_absents:

                    elements.append(
                        Paragraph(
                            f"- {j}",
                            styles["Normal"]
                        )
                    )

            else:

                elements.append(
                    Paragraph(
                        (
                            "Aucun jour ouvré "
                            "sans activité sur la période."
                        ),
                        styles["Normal"]
                    )
                )

            elements.append(
                Spacer(1, 15)
            )

        elements.append(
            Spacer(1, 20)
        )


    # ===============================
    # AGENTS SANS VENTE PAR SUPERVISEUR
    # ===============================
    elements.append(
        Paragraph(
            "<b>Agents actifs sans vente sur la période</b>",
            styles["Heading2"]
        )
    )
    
    agents_sans_vente_par_superviseur = defaultdict(list)

    for agent in agents_sans_vente:

        if agent.type_agent == "agent_gros":
            continue

        # Cas sans superviseur
        if not agent.superviseur:

            agents_sans_vente_par_superviseur[
                "sans_superviseur"
            ].append(agent)

            continue

        if not agent.superviseur.est_actif:
            continue

        if agent.superviseur.user.username == "jeanclaude.sup":
            continue

        agents_sans_vente_par_superviseur[
            agent.superviseur
        ].append(agent)
    
    for superviseur, agents in (
        agents_sans_vente_par_superviseur.items()
    ):
    
        if superviseur == "sans_superviseur":
        
            titre = "AGENTS SANS SUPERVISEUR"
    
        else:
        
            titre = (
                f"SUPERVISEUR : "
                f"{superviseur.full_name}"
            )
    
        elements.append(
            Paragraph(
                f"<b>{titre}</b>",
                styles["Heading3"]
            )
        )

    
        for agent in agents:
        
            texte = f"- {agent.full_name}"
    
            if agent.est_en_test:
            
                texte += (
                    f" ({agent.jours_restants_test} "
                    f"jours restants)"
                )
    
            elements.append(
                Paragraph(
                    texte,
                    styles["Normal"]
                )
            )
    
        elements.append(
            Spacer(1, 8)
        )
    # ===============================
    # BUILD PDF
    # ===============================
    doc.build(elements)
