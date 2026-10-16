"""Examinations: the approved result pattern, marks entry, ratings and result cards."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section, Subject
from apps.accounts.models import Scope
from apps.attendance.models import AttendanceRecord
from apps.exams import results as R
from apps.exams import services as S
from apps.exams.models import Exam, GradingScheme, Mark, Paper
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db
WEDNESDAY = dt.date(2026, 10, 14)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: WEDNESDAY)


@pytest.fixture
def setup(org, make_user):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    section = Section.objects.create(
        branch=org["samanabad"],
        session=org["session"],
        class_level=ClassLevel.objects.get(code="class-4"),
        name="A",
        class_teacher=teacher,
    )
    kids = []
    for n, name in enumerate(["Ali", "Sara", "Omar"], start=1):
        s = Student.objects.create(
            branch=org["samanabad"],
            admission_no=f"E-{n}",
            first_name=name,
            gender="male",
            admission_date=dt.date(2026, 4, 1),
        )
        Enrolment.objects.create(branch=s.branch, student=s, session=org["session"], section=section, roll_no=n)
        kids.append(s)
    mid = Exam.objects.create(session=org["session"], kind="mid", name="Mid-Term 2026-27")
    final = Exam.objects.create(session=org["session"], kind="final", name="Final 2026-27")
    english = Subject.objects.get(code="english")
    papers = {
        "mid": Paper.objects.create(exam=mid, class_level=section.class_level, subject=english, total_marks=50),
        "final": Paper.objects.create(exam=final, class_level=section.class_level, subject=english, total_marks=100),
    }
    return {"teacher": teacher, "section": section, "kids": kids, "papers": papers, "english": english, "mid": mid}


def scheme():
    return GradingScheme.objects.get(is_default=True)


def component(code):
    return scheme().components.get(code=code)


def give(setup, student, final=None, mid=None, mid_status="present", attendance=(23, 25), ratings=(5, 4, 5, 3)):
    """Fills in everything for one student. ratings = discipline, neatness, summer work, class work."""
    sec, t = setup["section"], setup["teacher"]
    if final is not None:
        S.save_marks(setup["papers"]["final"], sec, {student.pk: ("present", Decimal(final))}, t)
    if mid is not None or mid_status != "present":
        S.save_marks(
            setup["papers"]["mid"], sec, {student.pk: (mid_status, Decimal(mid) if mid is not None else None)}, t
        )
    present, total = attendance
    day = dt.date(2026, 9, 1)
    for i in range(total):
        AttendanceRecord.objects.create(
            branch=sec.branch,
            student=student,
            section=sec,
            date=day + dt.timedelta(days=i),
            status="present" if i < present else "absent",
            marked_by=t,
        )
    for code, value in zip(["discipline", "neatness", "summer_work", "class_work"], ratings, strict=True):
        if value is None:
            continue
        c = component(code)
        S.save_ratings(sec, c, None if c.scope == "student" else setup["english"], {student.pk: Decimal(value)}, t)


def result_for(setup, student, card="annual"):
    return next(r for r in R.section_results(setup["section"], card)["results"] if r.student == student)


def test_approved_pattern_is_seeded(seeded):
    codes = [(c.code, c.max_marks) for c in scheme().components.all()]
    assert codes == [
        ("final", 50),
        ("mid", 25),
        ("attendance", 5),
        ("discipline", 5),
        ("neatness", 5),
        ("summer_work", 5),
        ("class_work", 5),
    ]
    assert scheme().total == 100


def test_subject_score_follows_the_pattern(setup):
    ali = setup["kids"][0]
    give(setup, ali, final=80, mid=40, attendance=(23, 25), ratings=(5, 4, 5, 3))
    s = result_for(setup, ali).subjects[0]
    # Final 80/100 → 40 of 50; Mid 40/50 → 20 of 25; attendance 92% → 4; 5 + 4 + 5 + 3
    assert [
        s.parts[c].value for c in ("final", "mid", "attendance", "discipline", "neatness", "summer_work", "class_work")
    ] == [
        Decimal("40.00"),
        Decimal("20.00"),
        Decimal("4.00"),
        Decimal("5.00"),
        Decimal("4.00"),
        Decimal("5.00"),
        Decimal("3.00"),
    ]
    assert s.score == Decimal("81.00") and s.grade == "A+" and s.passed


def test_good_ratings_cannot_pass_a_failed_paper(setup):
    ali = setup["kids"][0]
    give(setup, ali, final=20, mid=10, attendance=(25, 25), ratings=(5, 5, 5, 5))
    s = result_for(setup, ali).subjects[0]
    assert s.score == Decimal("40.00")  # above 33 overall …
    assert s.exam_percent == Decimal("20.00")  # … but only 20% of exam marks
    assert s.passed is False


def test_mid_term_leave_lets_the_final_cover_its_share(setup):
    ali = setup["kids"][0]
    give(setup, ali, final=80, mid_status="excused")
    s = result_for(setup, ali).subjects[0]
    assert s.parts["final"].value == Decimal("60.00")  # 80% of (50 + 25)
    assert s.parts["mid"].value is None


def test_mid_term_absence_without_leave_counts_as_zero(setup):
    ali = setup["kids"][0]
    give(setup, ali, final=80, mid_status="absent")
    assert result_for(setup, ali).subjects[0].parts["mid"].value == Decimal("0")


def test_missing_items_make_the_result_incomplete(setup):
    ali = setup["kids"][0]
    give(setup, ali, final=80, mid=40, ratings=(5, None, 5, 3))
    r = result_for(setup, ali)
    assert not r.complete and r.subjects[0].missing == ["Neatness"]


def test_attendance_points_table(seeded):
    s, c = scheme(), component("attendance")
    assert [R.attendance_points(s, c, Decimal(p)) for p in (100, 95, 94.9, 85, 79, 74)] == [5, 5, 4, 3, 1, 0]


def test_positions_top_three_with_ties(setup):
    a, b, c = setup["kids"]
    give(setup, a, final=90, mid=45)
    give(setup, b, final=90, mid=45)
    give(setup, c, final=50, mid=25)
    positions = {r.student.first_name: r.position for r in R.section_results(setup["section"])["results"]}
    assert positions == {"Ali": 1, "Sara": 1, "Omar": 3}


def test_mid_term_report_uses_real_marks(setup):
    ali = setup["kids"][0]
    give(setup, ali, mid=37)
    r = result_for(setup, ali, card="mid")
    assert (r.obtained, r.maximum, r.percent, r.grade) == (Decimal("37.00"), Decimal(50), Decimal("74.00"), "A")


def test_teacher_enters_marks_with_checks(setup, login_as):
    client = login_as(setup["teacher"])
    paper, ali, sara = setup["papers"]["final"], *setup["kids"][:2]
    url = f"/exams/paper/{paper.pk}/section/{setup['section'].pk}/"
    body = client.post(url, {f"m{ali.pk}": "120", f"m{sara.pk}": "70"}).content.decode()
    assert "between 0 and 100" in body and not Mark.objects.exists()  # nothing saved
    client.post(url, {f"m{ali.pk}": "85.5", f"m{sara.pk}": "", f"st{sara.pk}": "absent"})
    assert Mark.objects.get(student=ali).obtained == Decimal("85.5")
    assert Mark.objects.get(student=sara).status == "absent"


def test_marks_entry_permissions(org, setup, make_user, login_as):
    paper, sec = setup["papers"]["final"], setup["section"]
    url = f"/exams/paper/{paper.pk}/section/{sec.pk}/"
    assert login_as(make_user("class_teacher", Scope.BRANCH, org["samanabad"])).get(url).status_code == 403
    paper.exam.marks_due_on = WEDNESDAY - dt.timedelta(days=1)
    paper.exam.save()
    assert login_as(setup["teacher"]).get(url).status_code == 403  # after the due date
    assert login_as(make_user("principal", Scope.BRANCH, org["samanabad"])).get(url).status_code == 200
    assert login_as(make_user("principal", Scope.BRANCH, org["lhr_franchise"])).get(url).status_code == 404


def test_teacher_ratings_screen(setup, login_as):
    client = login_as(setup["teacher"])
    ali = setup["kids"][0]
    url = f"/exams/section/{setup['section'].pk}/ratings/?component=neatness&subject={setup['english'].pk}"
    assert "between 0 and 5" in client.post(url, {f"r{ali.pk}": "7"}).content.decode()
    client.post(url, {f"r{ali.pk}": "4.5"})
    assert ali.ratings.get(component__code="neatness").value == Decimal("4.5")


def test_result_cards_render(setup, login_as):
    ali = setup["kids"][0]
    give(setup, ali, final=80, mid=40)
    client = login_as(setup["teacher"])
    sec = setup["section"]
    page = client.get(f"/exams/section/{sec.pk}/results/").content.decode()
    assert "Still missing" in page and "Ali" in page
    card = client.get(f"/exams/section/{sec.pk}/cards/{ali.pk}/").content.decode()
    assert "Annual Result Card" in card and "81" in card
    pdf = client.get(f"/exams/section/{sec.pk}/cards/?format=pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
