# core/pdf_compact.py
"""Mise en page PDF commune aux exports (reportlab) : A4 portrait, marges réduites, police
compacte, tableaux pleine largeur — pensé pour l'impression, avec un minimum de pages.
Les exports qui tracent des tableaux larges (beaucoup de colonnes) restent lisibles en 8 pt."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

MARGE = 1.2 * cm
TAILLE_TEXTE = 8
BLEU_ENTETE = colors.HexColor("#1F4E79")


def nouveau_document(buffer, title):
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGE, rightMargin=MARGE, topMargin=MARGE, bottomMargin=MARGE,
        title=title,
    )


def styles_compacts():
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = TAILLE_TEXTE
    styles["Normal"].leading = TAILLE_TEXTE + 2
    styles["BodyText"].fontSize = TAILLE_TEXTE
    styles["BodyText"].leading = TAILLE_TEXTE + 2
    styles["BodyText"].spaceBefore = 0
    styles["Title"].fontSize = 14
    styles["Title"].leading = 17
    styles["Title"].spaceAfter = 4
    styles["Heading2"].fontSize = 11
    styles["Heading2"].leading = 13
    styles["Heading2"].spaceBefore = 6
    styles["Heading2"].spaceAfter = 3
    styles["Heading3"].fontSize = 9
    styles["Heading3"].leading = 11
    styles["Heading3"].spaceBefore = 4
    styles["Heading3"].spaceAfter = 2
    return styles


def tableau(data, doc=None, fractions=None, extra_style=None):
    """Tableau compact (en-tête bleu, lignes alternées). `fractions` : parts de la largeur utile
    par colonne (ex. [3, 2, 1]) ; sans elle, les largeurs suivent le contenu."""
    col_widths = None
    if doc is not None and fractions:
        total = sum(fractions)
        col_widths = [doc.width * f / total for f in fractions]

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU_ENTETE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), TAILLE_TEXTE),
        ("LEADING", (0, 0), (-1, -1), TAILLE_TEXTE + 1),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        *(extra_style or []),
    ]))
    return table
