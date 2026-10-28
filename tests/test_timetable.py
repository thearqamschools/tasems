"""M7: subject teachers, bell times and timetables; a teacher is never in two classes at once."""

import datetime as dt

import pytest

from apps.academics import timetable as T
from apps.academics.models import ClassLevel, Period, Section, SectionSubject, Subject, TimetableEntry
from apps.accounts.models import Scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(org, make_user):
    branch, session = org["samanabad"], org["session"]
    four = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    five = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-5"), name="Rose"
    )
    principal = make_user("principal", Scope.BRANCH, branch, first_name="Pri")
    teacher = make_user("subject_teacher", Scope.BRANCH, branch, first_name="Aisha", last_name="Khan")
    p1 = Period.objects.create(branch=branch, number=1, starts_at=dt.time(8, 0), ends_at=dt.time(8, 40))
    Period.objects.create(
        branch=branch, number=2, label="Break", starts_at=dt.time(8, 40), ends_at=dt.time(9, 0), is_break=True
    )
    p3 = Period.objects.create(branch=branch, number=3, starts_at=dt.time(9, 0), ends_at=dt.time(9, 40))
    return {
        "branch": branch, "four": four, "five": five, "principal": principal, "teacher": teacher, "p1": p1, "p3": p3,
    }  # fmt: skip


def test_subject_teachers_are_saved_from_the_page(school, login_as):
    client = login_as(school["principal"])
    english = Subject.objects.get(code="english")
    page = client.get(f"/academics/section/{school['four'].id}/subjects/").content.decode()
    assert "English" in page and "Aisha Khan" in page
    client.post(f"/academics/section/{school['four'].id}/subjects/", {f"s_{english.id}": school["teacher"].id})
    assert SectionSubject.objects.get(section=school["four"], subject=english).teacher == school["teacher"]


def test_timetable_refuses_a_teacher_in_two_classes(school, login_as):
    english = Subject.objects.get(code="english")
    for s in (school["four"], school["five"]):
        SectionSubject.objects.create(branch=school["branch"], section=s, subject=english, teacher=school["teacher"])
    client = login_as(school["principal"])
    p1, p3 = school["p1"], school["p3"]
    client.post(f"/academics/section/{school['four'].id}/timetable/", {f"c_0_{p1.id}": english.id})
    assert TimetableEntry.objects.filter(section=school["four"]).count() == 1
    clash = client.post(f"/academics/section/{school['five'].id}/timetable/", {f"c_0_{p1.id}": english.id})
    assert "Aisha Khan already teaches Four-Rose" in clash.content.decode()
    assert not TimetableEntry.objects.filter(section=school["five"]).exists()
    client.post(f"/academics/section/{school['five'].id}/timetable/", {f"c_0_{p3.id}": english.id})
    week = T.teacher_grid(school["branch"], school["four"].session, school["teacher"])
    assert week["count"] == 2


def test_timetable_pages_and_menu(school, login_as):
    english = Subject.objects.get(code="english")
    SectionSubject.objects.create(
        branch=school["branch"], section=school["four"], subject=english, teacher=school["teacher"]
    )
    TimetableEntry.objects.create(
        branch=school["branch"], section=school["four"], weekday=0, period=school["p1"], subject=english
    )
    teacher = login_as(school["teacher"])
    mine = teacher.get("/academics/timetable/mine/").content.decode()
    assert "My timetable" in mine and "Four-Rose" in mine and 'href="/academics/timetable/mine/"' in mine
    assert teacher.post(f"/academics/section/{school['four'].id}/timetable/", {}).status_code == 403  # view only
    page = teacher.get(f"/academics/section/{school['four'].id}/timetable/").content.decode()
    assert "English" in page and "Break" in page and "Change timetable" not in page


def test_bell_times_page(school, login_as):
    client = login_as(school["principal"])
    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-0-number": "4",
        "form-0-starts_at": "10:00",
        "form-0-ends_at": "09:00",
    }
    bad = client.post("/academics/timetable/bell-times/", data)
    assert "must end after it starts" in bad.content.decode()
    data["form-0-ends_at"] = "10:40"
    client.post("/academics/timetable/bell-times/", data)
    assert Period.objects.filter(branch=school["branch"], number=4).exists()
