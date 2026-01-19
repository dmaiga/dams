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

@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={"class": css})



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