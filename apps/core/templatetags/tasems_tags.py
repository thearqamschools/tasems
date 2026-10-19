"""Small display filters shared by every module."""

from decimal import Decimal, InvalidOperation

from django import template

from apps.core.phone import format_cnic

register = template.Library()


@register.filter
def cnic(value):
    return format_cnic(value)


@register.filter
def rupees(value):
    """12500 → 12,500 ; 12500.5 → 12,500.50 ; empty → —"""
    if value in (None, ""):
        return "—"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if amount == amount.to_integral_value():
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


@register.filter
def bold(value):
    """Escapes text, then turns **words** into bold (used for printed instructions)."""
    import re

    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    return mark_safe(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(value or "")))


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if mapping else None


@register.filter
def sub(value, other):
    """a|sub:b → a − b (amounts in tables)."""
    return value - other


@register.filter
def split(value):
    """ "a b c"|split → ["a", "b", "c"] (lists of field names in templates)."""
    return value.split()


@register.filter
def field(form, name):
    """form|field:"name" → the bound field, or None when the form has no such field."""
    return form[name] if name in form.fields else None


@register.simple_tag
def icon(name, label=""):
    """An icon from the local Lucide sprite (static/icons/icons.svg). Decorative unless a label is given."""
    from django.templatetags.static import static
    from django.utils.html import format_html

    if label:
        return format_html(
            '<svg class="icon" role="img" aria-label="{}"><use href="{}#i-{}"></use></svg>',
            label,
            static("icons/icons.svg"),
            name,
        )
    return format_html(
        '<svg class="icon" aria-hidden="true" focusable="false"><use href="{}#i-{}"></use></svg>',
        static("icons/icons.svg"),
        name,
    )


@register.simple_tag
def official_logo(layout, media_base, font_base):
    """The logo uploaded in Setup if there is one, otherwise the official logo shipped with TASEMS
    (static/img/arqam-logo.png, used exactly as provided — never redrawn or recoloured)."""
    if layout is not None and getattr(layout, "left_logo", None):
        return f"{media_base}{layout.left_logo.name}"
    return f"{font_base[: -len('fonts/')]}img/arqam-logo-512.png"
