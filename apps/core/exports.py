"""Excel downloads and full-list printing for every list page (M5). The download always holds every row
that matches the page's filters, not just the page on screen."""

import datetime as dt
import io
from decimal import Decimal

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_ROWS = 50000
PRINT_MAX = 2000  # rows on one printed list


def wants_xlsx(request):
    return request.GET.get("format") == "xlsx"


def wants_print(request):
    return request.GET.get("print") == "1"


def paginate(request, items, per_page):
    """The usual page of a list, or every row (up to PRINT_MAX) when printing the whole list."""
    if wants_print(request):
        per_page = PRINT_MAX
    return Paginator(items, per_page).get_page(1 if wants_print(request) else request.GET.get("page"))


def _plain(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dt.datetime):
        return timezone.localtime(value).replace(tzinfo=None) if timezone.is_aware(value) else value
    if isinstance(value, (int, float, dt.date, str)):
        return value
    return str(value)


def xlsx_response(title, headers, rows, branch=None, filename=None):
    """One sheet: a title line (school, branch, list, date), then the headings and the rows."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = str(title)[:31].replace("/", "-")
    place = f" — {branch.name}" if branch else ""
    ws.append([f"The Arqam Schools{place}: {title}"])
    ws.append([f"Downloaded {timezone.localtime():%d %b %Y %H:%M}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([str(h) for h in headers])
    for cell in ws[3]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E8E9F5")  # --brand-soft
    widths = [len(str(h)) for h in headers]
    for count, row in enumerate(rows):
        if count >= MAX_ROWS:
            break
        values = [_plain(v) for v in row]
        ws.append(values)
        for i, v in enumerate(values[: len(widths)]):
            widths[i] = max(widths[i], len(v.strftime("%d %b %Y")) if isinstance(v, dt.date) else len(str(v)))
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            if isinstance(cell.value, dt.datetime):
                cell.number_format = "dd mmm yyyy hh:mm"
            elif isinstance(cell.value, dt.date):
                cell.number_format = "dd mmm yyyy"
            elif isinstance(cell.value, float):
                cell.number_format = "#,##0.##"
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 8), 45)
    ws.freeze_panes = "A4"
    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type=XLSX)
    name = filename or f"{slugify(str(title)) or 'list'}-{timezone.localdate():%Y-%m-%d}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response
