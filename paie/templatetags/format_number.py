from django import template

register = template.Library()

@register.filter
def number_dot(value):
    try:
        return "{:,.0f}".format(value).replace(",", ".")
    except Exception:
        return value
