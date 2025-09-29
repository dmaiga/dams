# templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def sub(value, arg):
    return value - arg

@register.filter
def multiply(value, arg):
    return value * arg