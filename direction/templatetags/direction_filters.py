# direction/templatetags/custom_filters.py
from django import template
from django.utils.formats import number_format
from decimal import Decimal

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