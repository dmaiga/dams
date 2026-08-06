# direction/templatetags/custom_filters.py
import re
from django import template
from django.utils.formats import number_format
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

register = template.Library()

@register.filter
def intcomma(value):
    """
    Convertit un nombre en format avec séparateurs de milliers
    Similaire au filtre intcomma de django.contrib.humanize
    """
    if value is None:
        return ''
    
    try:
        if isinstance(value, (int, float, Decimal)):
            # Formater avec séparateurs de milliers
            return "{:,.0f}".format(float(value)).replace(",", " ").replace(".", ",")
        else:
            # Essayer de convertir en nombre
            val = float(value)
            return "{:,.0f}".format(val).replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return value

@register.filter
def format_currency(value, currency="FCFA"):
    """
    Formate une valeur monétaire avec devise
    """
    if value is None:
        return f'0 {currency}'
    
    try:
        if isinstance(value, (int, float, Decimal)):
            formatted = "{:,.0f}".format(float(value)).replace(",", " ").replace(".", ",")
            return f"{formatted} {currency}"
        else:
            val = float(value)
            formatted = "{:,.0f}".format(val).replace(",", " ").replace(".", ",")
            return f"{formatted} {currency}"
    except (ValueError, TypeError):
        return f"0 {currency}"

@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={"class": css})

@register.filter
def multiply(value, arg):
    return value * arg

@register.filter
def percentage(value, decimals=2):
    """
    Formate un pourcentage
    """
    if value is None:
        return "0%"
    
    try:
        if isinstance(value, (int, float, Decimal)):
            return f"{value:.{decimals}f}%"
        else:
            val = float(value)
            return f"{val:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0%"
    

@register.filter
def get_item(dictionary, key):
    """Récupère un élément d'un dictionnaire par clé"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, Decimal('0.00'))
    return Decimal('0.00')

@register.filter
def sum_values(dictionary):
    """Calcule la somme des valeurs d'un dictionnaire"""
    if isinstance(dictionary, dict):
        return sum(value for value in dictionary.values() if isinstance(value, (int, float, Decimal)))
    return 0

@register.filter
def divide(value, divisor):
    """Divise une valeur par un diviseur"""
    try:
        divisor = float(divisor)
        if divisor == 0:
            return 0
        return float(value) / divisor
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def format_quantity(value):
    """Formate une quantité avec 2 décimales"""
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return "0.00"
    

@register.filter
def format_number(value):
    """
    - 8825.00 -> 8 825
    - 8825.50 -> 8 825,5
    - 8825.75 -> 8 825,75

    Arrondi à 2 décimales avant affichage : une division Decimal (ex. calcul de
    marge_pct) n'a aucune raison de se terminer proprement et peut produire jusqu'à
    28 chiffres significatifs (précision par défaut du module decimal) — sans cet
    arrondi, on affiche des valeurs du type "-79,17110617056084567305675574".
    """
    if value is None:
        return ""

    try:
        val = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        signe = "-" if val < 0 else ""
        val = abs(val)

        # Séparer partie entière / décimale
        int_part = int(val)
        decimal_part = val - int_part

        # Format milliers avec espace
        int_str = f"{int_part:,}".replace(",", " ")

        if decimal_part == 0:
            return f"{signe}{int_str}"

        # Supprimer les zéros inutiles
        decimal_str = f"{decimal_part:.2f}".split(".")[1].rstrip("0")

        return f"{signe}{int_str},{decimal_str}"

    except Exception:
        return value


@register.filter
def clean_engagement_label(value):
    """
    Retire l'identifiant technique parfois accolé en fin de libellé d'une
    Operation générée automatiquement côté dams_agro pour un engagement
    superviseur ↔ champ — ex. "Avance de trésorerie — 2" (2 = référence
    superviseur, un pk sans valeur métier pour la Direction) ou
    "Remboursement — Avance de trésorerie #17" (17 = pk technique de
    l'EngagementFinancier). Ni l'un ni l'autre n'est un besoin business —
    voir analyse_champ/views.py::operation_detail_view pour le commentaire
    réel de l'engagement, affiché séparément.
    """
    if not value:
        return value
    return re.sub(r'\s*(—\s*\d+|#\s*\d+)\s*$', '', str(value)).strip()


@register.filter
def short_datetime(value):

    if not value:
        return ''

    try:

        dt = datetime.fromisoformat(
            value.replace(
                'Z',
                '+00:00'
            )
        )

        return dt.strftime(
            '%d/%m/%y %H:%M'
        )

    except Exception:

        return value