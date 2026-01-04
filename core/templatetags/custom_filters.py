# templatetags/custom_filters.py
from django import template

register = template.Library()
from decimal import Decimal
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def sub(value, arg):
    return value - arg

@register.filter
def multiply(value, arg):
    return value * arg

@register.filter
def subtract(value, arg):
    """Soustrait arg de value"""
    try:
        return value - arg
    except Exception:
        return 0
    
@register.filter
def div(value, arg):
    """Division de value par arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0
    
@register.filter
def mul(value, arg):
    """Multiplie la valeur par l'argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
    


@register.filter
def sum_entrees(flux_list):
    """Somme des entrées"""
    total = Decimal('0.00')
    for flux in flux_list:
        if flux.get('flux') == 'ENTRÉE':
            try:
                montant = Decimal(str(flux.get('montant', 0)))
                total += montant
            except:
                continue
    return total

@register.filter
def sum_sorties(flux_list):
    """Somme des sorties"""
    total = Decimal('0.00')
    for flux in flux_list:
        if flux.get('flux') == 'SORTIE':
            try:
                montant = Decimal(str(flux.get('montant', 0)))
                total += montant
            except:
                continue
    return total

@register.filter
def sum_balance(flux_list):
    """Balance (entrées - sorties)"""
    return sum_entrees(flux_list) - sum_sorties(flux_list)

@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={"class": css})

register = template.Library()

@register.filter
def sum_attribute(queryset, attribute):
    """Somme d'un attribut sur un queryset/liste"""
    return sum(getattr(item, attribute, 0) for item in queryset)

@register.filter
def dictsum(queryset, field_name):
    """Somme les valeurs d'un champ dans un queryset"""
    total = Decimal('0.00')
    for item in queryset:
        value = getattr(item, field_name, None)
        if value is not None:
            try:
                total += Decimal(str(value))
            except:
                continue
    return total