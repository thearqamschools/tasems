"""Round 11 (project lead, 14 Nov 2026): Enter manually with salary and live net pay, search while typing, back links,
a clear staff-leaving step, EMP.code on salaries and bank details."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts.models import Scope
from apps.hr.models import Employee, Punch, StaffDay

from .test_round6 import staff  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_enter_manually_has_salary_and_live_net_pay(staff, login_as):  # noqa: F811
    page = login_as(staff["accountant"]).get("/payroll/manual/?month=2026-10").content.decode()
    heads = [page.index(h) for h in (">Use<", ">EMP.code<", ">Name<", ">Monthly salary<", ">Working days<",
                                     ">Half days<", ">Bonus days<", ">Net pay now (Rs)<")]  # fmt: skip
    assert heads == sorted(heads)
    g = staff["guard"]
    row = page[page.index(f'name="use_{g.id}"') - 600 :]
    assert 'data-rate="1000' in row and 'data-employed="31"' in row and "data-net" in page
    assert "31,000" in page  # the monthly salary shown


def test_search_while_typing_on_lists(staff, login_as, org):  # noqa: F811
    client = login_as(staff["director"])
    for url in ("/staff/", "/payroll/?month=2026-10", "/students/"):
        page = client.get(url).content.decode()
        assert 'data-live-search="#live-results"' in page and 'id="live-results"' in page
    found = client.get("/staff/?q=g1").content.decode()
    results = found[found.index('id="live-results"') :]
    assert "Staff G1" in results and "Staff T1" not in results  # part of the EMP.code, any case


def test_back_links_on_staff_pages(staff, login_as):  # noqa: F811
    client = login_as(staff["director"])
    for url in ("/staff/attendance/", "/staff/attendance/import/", "/staff/attendance/month/", "/staff/leave/"):
        page = client.get(url).content.decode()
        assert '<p><a href="/staff/">‹ Staff</a></p>' in page, url


def test_staff_member_leaving_and_taking_it_back(staff, login_as, org, make_user):  # noqa: F811
    t, b = staff["teacher"], staff["branch"]
    client = login_as(staff["director"])
    page = client.get(f"/staff/{t.id}/").content.decode()
    assert "Staff member is leaving" in page
    yesterday = dt.date(2026, 11, 4)
    StaffDay.objects.create(branch=b, employee=t, date=yesterday, status="absent")
    Punch.objects.create(branch=b, employee=t, created_by=staff["director"],
                         at=timezone.make_aware(dt.datetime(2026, 11, 2, 7, 40)))  # fmt: skip
    client.post(f"/staff/{t.id}/leaving/", {"left_on": "2026-11-03", "reason": "resigned", "note": "Moving city"})
    t.refresh_from_db()
    assert t.status == "resigned" and t.left_on == dt.date(2026, 11, 3) and t.leaving_note == "Moving city"
    assert not StaffDay.objects.filter(employee=t, date=yesterday).exists()  # nothing after the last day
    page = client.get(f"/staff/{t.id}/").content.decode()
    assert "Left on 03 Nov 2026 — Resigned" in page and "Final settlement" in page
    assert "Staff T1" not in client.get("/staff/").content.decode().split('id="live-results"')[1]
    assert "Staff T1" in client.get("/staff/?status=gone").content.decode()
    principal = login_as(make_user("principal", Scope.BRANCH, b))
    assert principal.post(f"/staff/{t.id}/leaving/", {"action": "undo"}).status_code == 403
    login_as(staff["director"]).post(f"/staff/{t.id}/leaving/", {"action": "undo"})
    t.refresh_from_db()
    assert t.status == Employee.Status.ACTIVE and t.left_on is None


def test_salaries_page_emp_code_first(staff, login_as):  # noqa: F811
    page = login_as(staff["accountant"]).get("/payroll/salaries/").content.decode()
    assert page.index(">EMP.code<") < page.index(">Name<")
    assert 'class="num center">G1</td>' in page
