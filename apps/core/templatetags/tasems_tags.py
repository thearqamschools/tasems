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


@register.simple_tag(takes_context=True)
def sort_th(context, key, label, css=""):
    """A table heading that sorts the list by `key`: first click ascending, second descending, with an arrow
    (project lead, 6 Nov 2026). Keeps the page's other filters; goes back to page 1."""
    from django.utils.html import format_html

    request = context["request"]
    current = request.GET.get("sort", "")
    params = request.GET.copy()
    params.pop("page", None)
    if current == key:
        params["sort"], arrow, order = f"-{key}", "▲", "ascending"
    elif current == f"-{key}":
        params["sort"], arrow, order = key, "▼", "descending"
    else:
        params["sort"], arrow, order = key, "", "none"
    return format_html(
        '<th class="{}" aria-sort="{}"><a class="sort" href="?{}">{}<span class="arrow" aria-hidden="true">{}</span>'
        "</a></th>",
        css,
        order,
        params.urlencode(),
        label,
        arrow,
    )


@register.filter
def days(value):
    """28.5 → 28.5 ; 31.0 → 31 ; empty → 0 (days may be halves since round 10)."""
    if value in (None, ""):
        return 0
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return value
    return int(number) if number == number.to_integral_value() else number.normalize()


@register.filter
def person_name(person):
    """A staff record's or a login's name (R17-8: teachers may be either)."""
    if not person:
        return ""
    if hasattr(person, "full_name"):
        return person.full_name
    return person.get_full_name() or person.username


CONTACT_ICONS = {  # Lucide shapes drawn inline, so they print in PDFs too (R18-2)
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1'
    "-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0"
    ' 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "mobile": '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
    "whatsapp": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M9.5 9.2c.3 2.2 2.1 4.2 4.6 5l1.2-1.1 1.6.8-.5 1.5'
    'c-3.8-.2-6.9-3.2-7.2-7l1.5-.5.8 1.6z" fill="currentColor" stroke="none"/>',
}
CONTACT_COLOURS = {"phone": "#3e4095", "mobile": "#3e4095", "whatsapp": "#1f9d55"}


@register.simple_tag
def contact_numbers(branch, separator="  "):
    """The branch's phones and mobiles, each with its mark: phone, mobile, or WhatsApp for a mobile ticked
    "On WhatsApp" in Setup → Branch details (R18-2)."""
    from django.utils.html import format_html, mark_safe

    parts = []
    for kind, number in getattr(branch, "contacts", []):
        svg = (
            f'<svg viewBox="0 0 24 24" width="1em" height="1em" style="vertical-align:-0.15em;margin-right:0.2em" '
            f'fill="none" stroke="{CONTACT_COLOURS[kind]}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-label="{kind}">{CONTACT_ICONS[kind]}</svg>'
        )
        span = '<span class="contact" style="white-space:nowrap">{}{}</span>'
        parts.append(format_html(span, mark_safe(svg), number))
    return mark_safe(separator.join(parts))


@register.filter
def keep_dash(value):
    """ "Periodic Assessment – II": the dash is tied to the words beside it, never alone on a line (R22-2)."""
    return str(value).replace(" – ", " – ")
