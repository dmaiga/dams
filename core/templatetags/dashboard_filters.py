# core/templatetags/dashboard_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(value, key):
    """Récupère un élément d'un dictionnaire ou liste de tuples par clé"""
    # Si c'est une liste de tuples comme mois_liste
    if isinstance(value, list) and value and isinstance(value[0], (tuple, list)):
        for k, v in value:
            if k == key:
                return v
        return ""
    
    # Si c'est un dictionnaire
    elif isinstance(value, dict):
        return value.get(key, "")
    
    # Si c'est autre chose (chaîne, etc.), retourner vide
    return ""

@register.filter
def div(value, arg):
    """Division de deux valeurs"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """Multiplication de deux valeurs"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sum_ca(produits):
    """Somme du CA des produits"""
    try:
        return sum(produit['ca'] for produit in produits)
    except (TypeError, KeyError):
        return 0

@register.filter
def avg_ca(tendance):
    """Moyenne du CA sur la tendance"""
    try:
        if not tendance:
            return 0
        return sum(item['ca'] for item in tendance) / len(tendance)
    except (TypeError, KeyError):
        return 0

@register.filter
def max_ca(tendance):
    """CA maximum dans la tendance"""
    try:
        if not tendance:
            return 0
        return max(item['ca'] for item in tendance)
    except (TypeError, KeyError, ValueError):
        return 0

@register.filter
def avg_rotation(stocks):
    """Rotation moyenne des stocks"""
    try:
        if not stocks:
            return 0
        rotations = [stock.get('taux_rotation', 0) for stock in stocks if stock.get('taux_rotation', 0) > 0]
        if not rotations:
            return 0
        return sum(rotations) / len(rotations)
    except (TypeError, KeyError):
        return 0

@register.filter
def first_letter(value):
    """Retourne la première lettre d'une chaîne"""
    try:
        return value[0].upper()
    except (TypeError, IndexError):
        return "?"

@register.filter
def safe_widthratio(numerator, denominator, max_value):
    """Version sécurisée de widthratio"""
    try:
        numerator = float(numerator)
        denominator = float(denominator)
        max_value = int(max_value)
        if denominator == 0:
            return 0
        return min((numerator / denominator) * max_value, max_value)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
    


@register.filter
def sum_attr(items, attr_name):
    """Somme d'un attribut sur une liste d'objets/dictionnaires"""
    try:
        if not items:
            return 0
        
        total = 0
        for item in items:
            # Si c'est un dictionnaire
            if isinstance(item, dict):
                total += item.get(attr_name, 0)
            # Si c'est un objet avec attributs
            elif hasattr(item, attr_name):
                value = getattr(item, attr_name)
                total += float(value) if value else 0
            # Si c'est un objet avec méthode get
            elif hasattr(item, 'get'):
                total += item.get(attr_name, 0)
        
        return total
    except (TypeError, AttributeError, ValueError):
        return 0
    

@register.filter
def filter_statut(stocks, statut_recherche):
    """Filtre les stocks par statut"""
    try:
        return [stock for stock in stocks if stock.get('statut') == statut_recherche]
    except (TypeError, AttributeError):
        return []

@register.filter
def percentage(part, total):
    """Calcule le pourcentage"""
    try:
        if total > 0:
            return (len(part) / total * 100)
        return 0
    except (TypeError, ZeroDivisionError):
        return 0
    
@register.filter
def filter_has_dette(fournisseurs_data):
    """Filtre les fournisseurs qui ont un reste à payer > 0"""
    return [f for f in fournisseurs_data if f.get('reste_a_payer', 0) > 0]