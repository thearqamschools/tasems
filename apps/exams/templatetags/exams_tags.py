from django import template

register = template.Library()


@register.filter
def get_part(parts, code):
    """parts dict lookup by component code, for result cards."""
    return parts.get(code) if parts else None
