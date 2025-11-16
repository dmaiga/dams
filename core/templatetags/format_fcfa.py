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
