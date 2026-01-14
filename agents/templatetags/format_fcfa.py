from django import template

register = template.Library()

@register.filter
def fcfa(value):
    try:
        value = float(value)
    except:
        return value
    
    # Format avec séparateur de milliers espace
    formatted = f"{value:,.0f}".replace(",", " ")

    return formatted 

@register.filter
def multiply(value, arg):
    """Multiplie la valeur par l'argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0