from django import template

from apps.core.utils import parse_iso

register = template.Library()


@register.filter
def format_datetime(value):
    """Renders an ISO timestamp string (as stored on HistoryEntry) as
    "dd/mm/YYYY HH:MM". Falls back to the raw value if it can't be parsed."""
    if not value:
        return ""
    try:
        return parse_iso(value).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return value
