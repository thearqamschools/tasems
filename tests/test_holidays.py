"""M7: the holiday calendar — students' holidays stop registers and diaries; staff holidays are not absences."""

import datetime as dt

import pytest

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.attendance import services as A
from apps.hr import services as H
from apps.hr.models import Holiday

pytestmark = pytest.mark.django_db
WED = dt.date(2026, 10, 14)


@pytest.fixture
def school(org, make_user):
    section = Section.objects.create(
        branch=org["samanabad"], session=org["session"], class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    return {
        "branch": org["samanabad"],
        "section": section,
        "principal": make_user("principal", Scope.BRANCH, org["samanabad"]),
    }


def test_principal_adds_a_branch_holiday_range(school, login_as):
    client = login_as(school["principal"])
    page = client.get("/academics/holidays/").content.decode()
    assert "Add a holiday" in page and "For every branch" not in page  # network holidays: head office only
    client.post(
        "/academics/holidays/",
        {
            "starts_on": "2026-10-14",
            "ends_on": "2026-10-15",
            "name": "Test holiday",
            "students_off": "on",
            "staff_off": "on",
        },
    )
    assert Holiday.objects.filter(branch=school["branch"]).count() == 2
    sections = Section.objects.filter(pk=school["section"].pk)
    assert not A.in_school(sections, WED).exists()
    assert not A.is_school_day(school["section"].class_level, WED, school["branch"].id)
    assert A.in_school(sections, dt.date(2026, 10, 16)).exists()
    assert "Test holiday" in client.get("/academics/holidays/").content.decode()


def test_staff_only_holiday_keeps_registers(school):
    Holiday.objects.create(branch=school["branch"], date=WED, name="Staff training", students_off=False, staff_off=True)
    assert A.in_school(Section.objects.filter(pk=school["section"].pk), WED).exists()
    assert WED in H.holidays(school["branch"], WED, WED)
    Holiday.objects.create(
        branch=school["branch"], date=WED + dt.timedelta(days=1), name="Parents day", staff_off=False
    )
    assert (WED + dt.timedelta(days=1)) not in H.holidays(school["branch"], WED, WED + dt.timedelta(days=1))


def test_network_holiday_by_head_office(school, login_as, make_user):
    admin = make_user("network_admin", Scope.NETWORK)
    client = login_as(admin)
    client.post(
        "/academics/holidays/",
        {
            "starts_on": "2026-12-25",
            "name": "Quaid-e-Azam Day",
            "students_off": "on",
            "staff_off": "on",
            "everywhere": "on",
        },
    )
    assert Holiday.objects.filter(branch__isnull=True, name="Quaid-e-Azam Day").exists()
    assert not A.in_school(Section.objects.all(), dt.date(2026, 12, 25)).exists()
    principal = login_as(school["principal"])
    h = Holiday.objects.get(branch__isnull=True)
    assert principal.post("/academics/holidays/", {"remove": h.id}).status_code == 403


def test_teacher_cannot_add(school, login_as, make_user):
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, school["branch"]))
    assert "Add a holiday" not in teacher.get("/academics/holidays/").content.decode()
    assert (
        teacher.post("/academics/holidays/", {"starts_on": "2026-10-20", "name": "X", "students_off": "on"}).status_code
        == 403
    )
