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
