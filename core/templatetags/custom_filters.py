# templatetags/custom_filters.py
from django import template

register = template.Library()

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