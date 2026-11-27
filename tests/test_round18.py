"""Round 18 (project lead, 26 Nov 2026): Class subjects from Classes and sections, WhatsApp tick for mobiles, several
bell-time sets by classes and campus, "Comp. Code", and the marks table in Comp. Code or Name order."""

import datetime as dt

import pytest

from apps.academics import timetable as T
from apps.academics.models import BellSet, ClassLevel, Period, SectionSubject, Subject, TimetableEntry
from apps.accounts.models import Scope
from apps.hr.models import Employee
from apps.organisation.models import Campus

from .test_exam_documents import exam_setup  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_class_subjects_button_and_whatsapp_tick(exam_setup, login_as, make_user):  # noqa: F811
    branch = exam_setup["branch"]
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    hub = admin.get("/setup/").content.decode()
    assert "Classes &amp; subjects" not in hub and "Classes & subjects" not in hub  # no separate card (R18-1)
    owner = login_as(make_user("branch_owner", Scope.BRANCH, branch))
    owner.post("/setup/branch-details/", {"name": branch.name, "address": "Sanora Colony", "phone": "041-2660265",
                                          "mobile_1": "0339-2406479", "mobile_1_whatsapp": "on",
                                          "mobile_2": "0300-1234567"})  # fmt: skip
    branch.refresh_from_db()
    assert branch.contacts == [("phone", "041-2660265"), ("whatsapp", "0339-2406479"), ("mobile", "0300-1234567")]
    from django.template import Context, Template

    html = Template("{% load tasems_tags %}{% contact_numbers b %}").render(Context({"b": branch}))
    assert 'aria-label="whatsapp"' in html and 'aria-label="mobile"' in html and 'aria-label="phone"' in html


def test_bell_time_sets_by_classes_and_campus(exam_setup, login_as):  # noqa: F811
    branch, four = exam_setup["branch"], exam_setup["section"]
    girls = Campus.objects.create(branch=branch, name="Girls", gender_group="girls")
    four.campus = girls
    four.save()
    pg, two, three, five = (ClassLevel.objects.get(code=c) for c in ("play-group", "class-2", "class-3", "class-5"))
    junior = BellSet.objects.create(branch=branch, name="Play Group to Two", from_level=pg, to_level=two)
    middle = BellSet.objects.create(branch=branch, name="Three to Five", from_level=three, to_level=five)
    middle_girls = BellSet.objects.create(
        branch=branch, name="Three to Five, girls", from_level=three, to_level=five, campus=girls
    )
    for bell, start in ((junior, 8), (middle, 8), (middle_girls, 9)):
        Period.objects.create(branch=branch, bell_set=bell, number=1, starts_at=dt.time(start, 0),
                              ends_at=dt.time(start, 40))  # fmt: skip
    assert T.bell_set_for(four) == middle_girls  # its campus before "every campus"
    assert [p.starts_at for p in T.periods_for(four)] == [dt.time(9, 0)]
    client = login_as(exam_setup["principal"])
    page = client.get("/academics/timetable/bell-times/").content.decode()
    assert "Three to Five, girls" in page and "Add bell times" in page


def test_teacher_clash_by_clock_time_across_sets(exam_setup):  # noqa: F811
    from apps.academics.models import Section

    branch, four = exam_setup["branch"], exam_setup["section"]
    level5 = ClassLevel.objects.get(code="class-5")
    five = Section.objects.create(branch=branch, session=four.session, class_level=level5, name="Lily")
    a = BellSet.objects.create(branch=branch, name="A", to_level=ClassLevel.objects.get(code="class-4"))
    b = BellSet.objects.create(branch=branch, name="B", from_level=ClassLevel.objects.get(code="class-5"))
    pa = Period.objects.create(branch=branch, bell_set=a, number=1, starts_at=dt.time(8, 0), ends_at=dt.time(8, 40))
    pb = Period.objects.create(branch=branch, bell_set=b, number=1, starts_at=dt.time(8, 20), ends_at=dt.time(9, 0))
    english = Subject.objects.get(code="english")
    teacher = Employee.objects.create(
        branch=branch, code="T5", full_name="Rabia", gender="female", designation="Teacher", staff_type="teaching",
        joined_on=dt.date(2026, 4, 1),
    )  # fmt: skip
    for s in (four, five):
        SectionSubject.objects.create(branch=branch, section=s, subject=english, teacher_staff=teacher)
    TimetableEntry.objects.create(branch=branch, section=four, weekday=0, period=pa, subject=english)
    with pytest.raises(ValueError):  # 8:20–9:00 meets 8:00–8:40 although the period numbers are in other sets
        T.save_grid(five, {(0, pb.id): english}, exam_setup["principal"])


def test_comp_code_and_sorting_the_marks_table(exam_setup, login_as):  # noqa: F811
    client = login_as(exam_setup["principal"])
    url = f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/marks/"
    page = client.get(f"{url}?sort=-code").content.decode()
    assert "Comp. Code" in page and "COMP.code" not in page
    assert page.index("Slip1") < page.index("Slip0")  # 601 before 600
    by_name = client.get(f"{url}?sort=name").content.decode()
    assert by_name.index("Slip0") < by_name.index("Slip1")
