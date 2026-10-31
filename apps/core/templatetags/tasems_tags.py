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
def short_campus(campus):
    """ "Girls Campus" → "Girls" in tables, so the cell stays on one line (project lead, 31 Oct 2026)."""
    name = getattr(campus, "name", campus) or ""
    for tail in (" Campus", " campus"):
        name = name.removesuffix(tail)
    return name


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


@register.simple_tag(takes_context=True)
def list_url(context, **extra):
    """This page's address with its filters, without the page number, plus `extra` (e.g. format="xlsx")."""
    params = context["request"].GET.copy()
    for key in ("page", "format", "print"):
        params.pop(key, None)
    for key, value in extra.items():
        params[key] = value
    return "?" + params.urlencode()


@register.simple_tag(takes_context=True)
def delete_button(context, kind, obj):
    """A Delete button for a record made by mistake, shown only to people allowed to delete it."""
    from django.urls import reverse
    from django.utils.html import format_html
    from django.utils.translation import gettext as _

    from apps.core import deletion

    request = context.get("request")
    if obj is None or getattr(obj, "pk", None) is None or request is None:
        return ""
    if not deletion.can_delete(request.user, kind, obj):
        return ""
    url = reverse("delete_record", args=[kind, obj.pk]) + "?back=" + request.path
    return format_html('<a class="button danger quiet" href="{}">{}{}</a>', url, icon("x"), _("Delete"))
