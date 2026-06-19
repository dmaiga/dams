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
    # REGROUPEMENT & FILTRES MÉTIERS
    # ===============================
    from core.models import Agent

    # Structures distinctes pour séparer la hiérarchie classique des agents spéciaux
    superviseurs = defaultdict(
        lambda: {
            "superviseur": None,
            "agents": defaultdict(list)
        }
    )
    agents_speciaux_actifs = defaultdict(list)

    agents_cache = {}

    # 1. Traitement du flux des ventes (Rapport)
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

        # CAS UNIQUE : Agents spéciaux (Gros et Polyvalents) -> Section Dédiée
        if agent.type_agent in ["agent_gros", "agent_polivalent"]:
            superviseurs["agents_speciaux"]["superviseur"] = "SPECIAL"
            superviseurs["agents_speciaux"]["agents"][agent.id].append(row)
            continue

        # Filtrage de sécurité sur la hiérarchie standard (uniquement les agents de terrain)
        if agent.type_agent != "terrain":
            continue

        superviseur = agent.superviseur

        # CAS A : Agent de terrain sans superviseur affecté
        if not superviseur:
            superviseurs["sans_superviseur"]["superviseur"] = None
            superviseurs["sans_superviseur"]["agents"][agent.id].append(row)
            continue

        # CAS B : Filtres d'exclusions sur les superviseurs
        if superviseur.user.username == "jeanclaude.sup" or not superviseur.est_actif or superviseur.type_agent != "entrepot":
            continue

        # CAS C : Flux normal (Superviseur valide + Agent terrain)
        superviseurs[superviseur.id]["superviseur"] = superviseur
        superviseurs[superviseur.id]["agents"][agent.id].append(row)

    # ===============================
    # AFFICHAGE DU CORPS DES VENTES
    # ===============================
    # Pour garantir la structure d'affichage, on traite les superviseurs classiques puis les agents spéciaux
    ordres_sections = sorted(
        [k for k in superviseurs.keys() if k not in ["sans_superviseur", "agents_speciaux"]]
    )
    if "sans_superviseur" in superviseurs:
        ordres_sections.append("sans_superviseur")
    if "agents_speciaux" in superviseurs:
        ordres_sections.append("agents_speciaux")

    for section_key in ordres_sections:
        superviseur_data = superviseurs[section_key]
        superviseur = superviseur_data["superviseur"]
        agents = superviseur_data["agents"]

        # ----------------------------------
        # TITRE DE LA SECTION
        # ----------------------------------
        if superviseur == "SPECIAL":
            titre_superviseur = "AGENTS SPÉCIAUX (GROS & POLYVALENTS)"
        elif superviseur:
            titre_superviseur = f"SUPERVISEUR : {superviseur.full_name.upper()}"
        else:
            titre_superviseur = "AGENTS SANS SUPERVISEUR"

        # ----------------------------------
        # CALCUL DES STATISTIQUES DE L'ÉQUIPE
        # ----------------------------------
        total_equipe = 0
        for ventes in agents.values():
            total_equipe += sum(float(v["total_kg"]) for v in ventes)

        nb_agents_vendeurs = len(agents)

        if superviseur == "SPECIAL":
            # Compter tous les agents spéciaux actifs en BDD pour le calcul du ratio
            nb_agents_actifs = Agent.objects.filter(
                type_agent__in=["agent_gros", "agent_polivalent"],
                est_actif=True
            ).count()
            nb_agents_sans_vente = max(0, nb_agents_actifs - nb_agents_vendeurs)
        elif superviseur:
            nb_agents_actifs = (
                superviseur.agents_geres
                .filter(est_actif=True)
                .filter(type_agent="terrain")  # Strictement limité au terrain ici
                .count()
            )
            nb_agents_sans_vente = max(0, nb_agents_actifs - nb_agents_vendeurs)
        else:
            nb_agents_actifs = len(agents)
            nb_agents_sans_vente = 0

        elements.append(Paragraph(f"<b>{titre_superviseur}</b>", styles["Heading1"]))
        elements.append(Paragraph(
            (
                f"Agents actifs : {nb_agents_actifs}<br/>"
                f"Agents ayant vendu : {nb_agents_vendeurs}<br/>"
                f"Agents sans vente : {nb_agents_sans_vente}<br/>"
                f"Total équipe : {total_equipe:.2f} kg"
            ),
            styles["Normal"]
        ))
        elements.append(Spacer(1, 12))

        # ====================================
        # BOUCLE DETAILS AGENTS
        # ====================================
        for agent_id, ventes in agents.items():
            agent_obj = agents_cache[agent_id]
            agent_nom = f"{agent_obj.user.first_name} {agent_obj.user.last_name}"
            
            # Ajout du tag de rôle à côté du nom pour les agents spéciaux
            role_tag = f" ({agent_obj.get_type_agent_display()})" if agent_obj.type_agent in ["agent_gros", "agent_polivalent"] else ""
            total_agent_kg = sum(float(v["total_kg"]) for v in ventes)

            if agent_obj.est_en_test:
                titre = (
                    f"Agent : {agent_nom}{role_tag} "
                    f"(EN TEST - {agent_obj.jours_restants_test} jours restants)"
                    f" — Total période : {total_agent_kg:.2f} kg"
                )
            else:
                titre = f"Agent : {agent_nom}{role_tag} — Total période : {total_agent_kg:.2f} kg"

            elements.append(Paragraph(f"<b>{titre}</b>", styles["Heading2"]))
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

            # Remplissage du tableau des ventes de l'agent
            for v in ventes:
                jour = v["date_vente__date"]
                kg = float(v["total_kg"])
                jours_vendus.add(jour)
                totaux_par_jour[jour] += kg

                if jour != dernier_jour:
                    data.append([
                        Paragraph(format_date_courte_fr(jour), style_date),
                        "",
                        ""
                    ])
                    dernier_jour = jour

                poids_unitaire = v["detail_distribution__lot__produit__poids_unitaire_kg"]
                quantite_affichee = str(v["total_quantite"]) if poids_unitaire else "-"

                data.append([
                    Paragraph(v["detail_distribution__lot__produit__nom"], style_produit),
                    Paragraph(quantite_affichee, style_num),
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

            # Totaux journaliers
            elements.append(Paragraph("<b>Total vendu par jour</b>", styles["Heading3"]))
            for jour, total in sorted(totaux_par_jour.items()):
                elements.append(Paragraph(f"{format_date_courte_fr(jour)} : {total:.2f} kg", styles["Normal"]))

            # Jours d'inactivité
            jours_absents = jours_non_travailles_individuels(date_debut, date_fin, jours_vendus)
            elements.append(Paragraph("<b>Jours sans activité</b>", styles["Heading3"]))
            if jours_absents:
                for j in jours_absents:
                    elements.append(Paragraph(f"- {j}", styles["Normal"]))
            else:
                elements.append(Paragraph("Aucun jour ouvré sans activité sur la période.", styles["Normal"]))

            elements.append(Spacer(1, 15))
        elements.append(Spacer(1, 20))

    # ==========================================
    # SECTION FINALE : AGENTS ACTIFS SANS VENTE
    # ==========================================
    elements.append(Paragraph("<b>Agents actifs sans vente sur la période</b>", styles["Heading2"]))
    
    agents_sans_vente_par_superviseur = defaultdict(list)

    for agent in agents_sans_vente:
        # Séparation et redirection des agents spéciaux sans vente
        if agent.type_agent in ["agent_gros", "agent_polivalent"]:
            agents_sans_vente_par_superviseur["agents_speciaux"].append(agent)
            continue

        if agent.type_agent != "terrain":
            continue

        if not agent.superviseur:
            agents_sans_vente_par_superviseur["sans_superviseur"].append(agent)
            continue

        if not agent.superviseur.est_actif or agent.superviseur.user.username == "jeanclaude.sup":
            continue

        agents_sans_vente_par_superviseur[agent.superviseur].append(agent)
    
    # Tri d'affichage pour la clarté du PDF
    ordres_sans_vente = sorted(
        [k for k in agents_sans_vente_par_superviseur.keys() if isinstance(k, Agent)],
        key=lambda x: x.full_name
    )
    if "sans_superviseur" in agents_sans_vente_par_superviseur:
        ordres_sans_vente.append("sans_superviseur")
    if "agents_speciaux" in agents_sans_vente_par_superviseur:
        ordres_sans_vente.append("agents_speciaux")

    for key in ordres_sans_vente:
        agents = agents_sans_vente_par_superviseur[key]
        
        if key == "agents_speciaux":
            titre = "AGENTS SPÉCIAUX (GROS & POLYVALENTS)"
        elif key == "sans_superviseur":
            titre = "AGENTS SANS SUPERVISEUR"
        else:
            titre = f"SUPERVISEUR : {key.full_name.upper()}"
    
        elements.append(Paragraph(f"<b>{titre}</b>", styles["Heading3"]))
    
        for agent in agents:
            role_tag = f" ({agent.get_type_agent_display()})" if agent.type_agent in ["agent_gros", "agent_polivalent"] else ""
            texte = f"- {agent.full_name}{role_tag}"
    
            if agent.est_en_test:
                texte += f" ({agent.jours_restants_test} jours restants)"
    
            elements.append(Paragraph(texte, styles["Normal"]))
    
        elements.append(Spacer(1, 8))

    # Build complet
    doc.build(elements)