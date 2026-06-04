from datetime import datetime

from django import template


register = template.Library()


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