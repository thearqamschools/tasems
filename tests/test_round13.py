"""Round 13 (project lead, 19 Nov 2026): side menu (one group open, capital first letters, School Fee group),
monthly sheet key / alignment / downloads, and a day report on Staff attendance."""

import io
import re

import pytest
from openpyxl import load_workbook

from apps.accounts.context_processors import title_case

from .test_round6 import staff  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_title_case_keeps_small_words_small():
    assert title_case("Needs attention") == "Needs Attention"
    assert title_case("Admission inquiries") == "Admission Inquiries"
    assert title_case("Import from Excel") == "Import from Excel"
    assert title_case("Cash & bank book") == "Cash & Bank Book"
    assert title_case("CV bank") == "CV Bank"
    assert title_case("Add a CV") == "Add a CV"


def test_menu_has_school_fee_group_and_capitals(staff, login_as):  # noqa: F811
    page = login_as(staff["director"]).get("/staff/").content.decode()
    labels = re.findall(r'class="nav-group-label"[^>]*>([^<]+)<', page)
    assert "School Fee" in labels and "Finance" in labels
    assert labels.index("School Fee") == labels.index("Finance") - 1
    assert "Staff Attendance" in page and "Monthly Sheet" in page
    js = open("static/js/tasems.js").read()
    assert "one open at a time" in js


def test_monthly_sheet_key_downloads_and_centred_rows(staff, login_as):  # noqa: F811
    client = login_as(staff["director"])
    page = client.get("/staff/attendance/month/?month=2026-10").content.decode()
    assert page.index('class="mark-key"') < page.index("report-tools") < page.index("month-sheet")
    for k in ("P = Present", "L = Late", "H = Half Day", "LV = Leave", "HD = Holiday", "e = Early Left"):
        assert k in page
    assert 'class="name center"' in page
    assert "format=pdf" in page and "format=xlsx" in page and "print=1" in page
    pdf = client.get("/staff/attendance/month/?month=2026-10&format=pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    printed = client.get("/staff/attendance/month/?month=2026-10&print=1").content.decode()
    assert "MONTHLY STAFF ATTENDANCE" in printed and "window.print()" in printed
    wb = load_workbook(io.BytesIO(client.get("/staff/attendance/month/?month=2026-10&format=xlsx").content))
    assert any("P = Present" in str(c.value) for row in wb.active.iter_rows() for c in row if c.value)


def test_day_report_print_pdf_excel(staff, login_as):  # noqa: F811
    client = login_as(staff["director"])
    page = client.get("/staff/attendance/?date=2026-10-05").content.decode()
    assert 'class="heading-tools"' in page and "format=pdf" in page
    pdf = client.get("/staff/attendance/?date=2026-10-05&format=pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    printed = client.get("/staff/attendance/?date=2026-10-05&print=1").content.decode()
    assert "STAFF ATTENDANCE" in printed and "Nothing Recorded" in printed
    assert "Nothing recorded" in printed  # staff with no record yet are listed, not marked absent
    wb = load_workbook(io.BytesIO(client.get("/staff/attendance/?date=2026-10-05&format=xlsx").content))
    values = [c.value for row in wb.active.iter_rows() for c in row]
    assert "Nothing Recorded" in values and "EMP.code" in values
