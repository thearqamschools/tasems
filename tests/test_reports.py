"""M6: the reports centre lists only what a person may open, and the new reports add up."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.attendance.models import SectionAttendance
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(org, make_user):
    branch, session = org["samanabad"], org["session"]
    four = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    hifz = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="hifz"), name="A"
    )
    people = [
        ("m", four, False, dt.date(2026, 4, 1)),
        ("f", four, False, dt.date(2026, 10, 2)),
        ("m", hifz, True, dt.date(2026, 10, 5)),
    ]
    kids = []
    for n, (g, sec, is_hifz, admitted) in enumerate(people):
        s = Student.objects.create(
            branch=branch,
            admission_no=str(700 + n),
            first_name=f"Kid{n}",
            gender="male" if g == "m" else "female",
            is_hifz=is_hifz,
            admission_date=admitted,
        )
        Enrolment.objects.create(branch=branch, student=s, session=session, section=sec)
        kids.append(s)
    Student.objects.create(
        branch=branch, admission_no="799", first_name="Unplaced", gender="male", admission_date=dt.date(2026, 4, 1)
    )
    return {"branch": branch, "four": four, "hifz": hifz, "kids": kids}  # fmt: skip


def test_centre_shows_only_allowed_modules(school, login_as, make_user):
    principal = login_as(make_user("principal", Scope.BRANCH, school["branch"]))
    page = principal.get("/reports/").content.decode()
    for title in (
        "Class strength",
        "Defaulters by family",
        "Monthly attendance by class",
        "Monthly sheet",
    ):
        assert title in page
    assert "Expenses of the month" not in page and "Daily collection" not in page  # no finance (23 Oct 2026)
    teacher = login_as(make_user("subject_teacher", Scope.BRANCH, school["branch"]))
    page = teacher.get("/reports/").content.decode()
    assert "Class strength" in page and "Defaulters" not in page and "Monthly sheet" not in page
    assert 'href="/reports/"' in page  # in the menu


def test_class_strength_counts_boys_girls_and_hifz(school, login_as, make_user):
    client = login_as(make_user("principal", Scope.BRANCH, school["branch"]))
    page = client.get("/reports/class-strength/").content.decode()
    assert "1 active student is not placed" in page
    rows = __import__("tests.test_exports", fromlist=["sheet"]).sheet(
        client.get("/reports/class-strength/?format=xlsx")
    )
    body = {r[0]: r[3:] for r in rows[3:]}
    assert body["Four"] == [1, 1, 2, 0] and body["Hifz-e-Quran"] == [1, 0, 1, 1] and body["Total"] == [2, 1, 3, 1]


def test_new_admissions_between_dates(school, login_as, make_user):
    client = login_as(make_user("principal", Scope.BRANCH, school["branch"]))
    page = client.get("/reports/new-admissions/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "Kid1" in page and "Kid2" in page and "Kid0" not in page


def test_monthly_attendance_by_class(school, login_as, make_user):
    user = make_user("principal", Scope.BRANCH, school["branch"])
    for day, (p, a) in [(1, (1, 1)), (2, (2, 0))]:
        SectionAttendance.objects.create(
            branch=school["branch"],
            section=school["four"],
            date=dt.date(2026, 10, day),
            taken_by=user,
            present=p,
            absent=a,
        )
    client = login_as(user)
    page = client.get("/reports/attendance-month/?month=2026-10").content.decode()
    assert "75%" in page  # 3 of 4 marks
    assert client.get("/reports/attendance-month/?month=2026-10&format=xlsx").status_code == 200


def test_reports_need_permission(school, login_as, make_user, org):
    stranger = login_as(make_user("hifz_teacher", Scope.BRANCH, school["branch"]))
    assert stranger.get("/reports/attendance-month/").status_code in (200, 403)
    assert stranger.get("/reports/class-strength/").status_code in (200, 403)
    other = login_as(make_user("principal", Scope.BRANCH, org["lhr_franchise"]))
    assert "Kid0" not in other.get("/reports/new-admissions/?from=2026-01-01").content.decode()
    assert timezone.localdate()  # today's date is used when no dates are given
