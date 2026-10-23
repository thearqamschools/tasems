"""M13 (free part): students needing attention — plain rules over attendance, marks, fees and Hifz."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section, Subject
from apps.accounts.models import Scope
from apps.attendance.models import AttendanceRecord
from apps.exams.models import Exam, Mark, Paper
from apps.fees import services as fees
from apps.fees.models import FeeHead
from apps.hifz.models import HifzLesson
from apps.insights import services as S
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 10, 23)  # a Friday


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: TODAY)


@pytest.fixture
def school(org, make_user):
    branch, session = org["samanabad"], org["session"]
    teacher = make_user("class_teacher", Scope.BRANCH, branch)
    section = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-4"), name="A",
        class_teacher=teacher,
    )  # fmt: skip
    other = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-5"), name="B"
    )
    kids = {}
    for name, sec in [("Absent", section), ("Weak", section), ("Fine", section), ("Elsewhere", other)]:
        s = Student.objects.create(
            branch=branch, admission_no=str(700 + len(kids)), first_name=name, gender="male",
            admission_date=dt.date(2026, 4, 1),
        )  # fmt: skip
        Enrolment.objects.create(branch=branch, student=s, session=session, section=sec)
        kids[name] = s
    principal = make_user("principal", Scope.BRANCH, branch)
    days = [TODAY - dt.timedelta(days=n) for n in range(1, 30) if (TODAY - dt.timedelta(days=n)).weekday() != 6]
    for d in days:  # about 25 school days before today
        for name, s in kids.items():
            sec = other if name == "Elsewhere" else section
            status = "absent" if (name == "Absent" and d >= TODAY - dt.timedelta(days=3)) else "present"
            if name == "Elsewhere":
                status = "absent" if d.day % 2 else "present"  # every other day: low attendance, no streak
            AttendanceRecord.objects.create(
                branch=branch, student=s, section=sec, date=d, status=status, marked_by=principal
            )
    return {"branch": branch, "session": session, "section": section, "other": other, "kids": kids,
            "teacher": teacher, "principal": principal}  # fmt: skip


def flags(rows, name):
    return {code for r in rows if r.student.first_name == name for code, _t in r.flags}


def test_absence_streak_and_low_attendance(school):
    rows = S.students_needing_attention(school["branch"], school["session"], TODAY, S.read_limits({}))
    assert flags(rows, "Absent") == {"streak"}  # 3 school days absent, attendance still high
    assert flags(rows, "Elsewhere") == {"attendance"}
    assert not flags(rows, "Fine")
    strict = S.students_needing_attention(school["branch"], school["session"], TODAY, S.read_limits({"streak": "4"}))
    assert "streak" not in flags(strict, "Absent")
    assert S.read_limits({"streak": "abc", "attendance": "500"}) == {**S.DEFAULTS, "attendance": 100}


def test_falling_marks_and_below_pass(school):
    english = Subject.objects.get(code="english")
    level = school["section"].class_level
    weak = school["kids"]["Weak"]
    for when, name, got in [(dt.date(2026, 9, 1), "Test 1", 40), (dt.date(2026, 10, 10), "Mid-Term", 15)]:
        exam = Exam.objects.create(session=school["session"], kind="test", name=name, starts_on=when)
        paper = Paper.objects.create(exam=exam, class_level=level, subject=english, total_marks=50)
        Mark.objects.create(
            branch=school["branch"], paper=paper, student=weak, section=school["section"], obtained=got,
            entered_by=school["principal"],
        )  # fmt: skip
    rows = S.students_needing_attention(school["branch"], school["session"], TODAY, S.read_limits({}))
    weak_row = next(r for r in rows if r.student == weak)
    texts = " ".join(t for _c, t in weak_row.flags)
    assert {c for c, _t in weak_row.flags} == {"below_pass", "drop"}
    assert "80%" in texts and "30%" in texts and "pass mark 33%" in texts


def test_fees_and_hifz_signals_need_their_permission(school, make_user):
    kid = school["kids"]["Fine"]
    head = FeeHead.objects.get(kind=FeeHead.Kind.MONTHLY)
    for month in (dt.date(2026, 9, 1), dt.date(2026, 10, 1)):
        fees.add_charge(kid, head, month, 4000, school["principal"])
    for n in range(3):
        HifzLesson.objects.create(
            branch=school["branch"], student=kid, date=TODAY - dt.timedelta(days=n + 1), status="not_ready",
            recorded_by=school["principal"],
        )  # fmt: skip
    plain = S.students_needing_attention(school["branch"], school["session"], TODAY, S.read_limits({}))
    assert not flags(plain, "Fine")  # no fee or Hifz rights: those signals are not worked out
    full = S.students_needing_attention(
        school["branch"], school["session"], TODAY, S.read_limits({}), can_fees=True, can_hifz=True
    )
    assert flags(full, "Fine") == {"fees", "not_ready"}


def test_page_teacher_sees_own_class_principal_all(school, login_as, make_user):
    teacher = login_as(school["teacher"])
    page = teacher.get("/attention/")
    names = {r.student.first_name for r in page.context["rows"]}
    assert names == {"Absent"} and 'href="/attention/"' in page.content.decode()  # not class 5-B
    principal = login_as(school["principal"])
    page = principal.get("/attention/")
    assert {r.student.first_name for r in page.context["rows"]} == {"Absent", "Elsewhere"}
    assert "Fee unpaid" in page.content.decode()  # principals see fees
    only = principal.get("/attention/?signal=attendance")
    assert [r.student.first_name for r in only.context["rows"]] == ["Elsewhere"]
    xlsx = principal.get("/attention/?format=xlsx")
    assert xlsx["Content-Type"].startswith("application/vnd.openxml")
    accountant = login_as(make_user("accountant", Scope.BRANCH, school["branch"]))
    assert accountant.get("/attention/").status_code == 403
