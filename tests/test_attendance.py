"""Daily attendance: once a day, per section."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.attendance.models import AttendanceRecord, SectionAttendance
from apps.attendance.services import absence_streaks, save_register
from apps.core.models import AuditEvent
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

pytestmark = pytest.mark.django_db


@pytest.fixture
def klass(org, make_user):
    """Class 5-A at Samanabad with a class teacher and three students."""
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    section = Section.objects.create(
        branch=org["samanabad"],
        session=org["session"],
        class_level=ClassLevel.objects.get(code="class-5"),
        name="A",
        class_teacher=teacher,
    )
    kids = []
    for n, name in enumerate(["Ahmed", "Bilal", "Daniyal"], start=1):
        s = Student.objects.create(
            branch=org["samanabad"],
            admission_no=f"K-{n}",
            first_name=name,
            gender="male",
            admission_date=dt.date(2026, 4, 1),
        )
        Enrolment.objects.create(branch=s.branch, student=s, session=org["session"], section=section, roll_no=n)
        kids.append(s)
    parent = Guardian.objects.create(branch=org["samanabad"], full_name="Parent", phone="03001112223")
    StudentGuardian.objects.create(student=kids[1], guardian=parent, relationship="father", is_primary_contact=True)
    return {"section": section, "teacher": teacher, "kids": kids}


def url(section, day=None):
    return f"/attendance/section/{section.pk}/{(day or timezone.localdate()).isoformat()}/"


def test_teacher_takes_register_with_absentees_only_tapped(klass, login_as):
    client = login_as(klass["teacher"])
    page = client.get(url(klass["section"]))
    assert page.status_code == 200 and "Daniyal" in page.content.decode()
    bilal = klass["kids"][1]
    response = client.post(url(klass["section"]), {f"s{bilal.pk}": "absent", f"n{bilal.pk}": "Fever"})
    assert response.status_code == 302
    register = SectionAttendance.objects.get(section=klass["section"], date=timezone.localdate())
    assert (register.present, register.absent, register.total) == (2, 1, 3)
    assert AttendanceRecord.objects.get(student=bilal).note == "Fever"


def test_teacher_cannot_take_another_teachers_section(org, klass, make_user, login_as):
    other = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    assert login_as(other).get(url(klass["section"])).status_code == 403


def test_teacher_cannot_change_yesterday_but_principal_can(org, klass, make_user, login_as):
    yesterday = timezone.localdate() - dt.timedelta(days=1)
    assert login_as(klass["teacher"]).get(url(klass["section"], yesterday)).status_code == 403
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    assert login_as(principal).get(url(klass["section"], yesterday)).status_code == 200


def test_future_dates_are_refused(klass, login_as):
    tomorrow = timezone.localdate() + dt.timedelta(days=1)
    assert login_as(klass["teacher"]).get(url(klass["section"], tomorrow)).status_code == 404


def test_other_branch_cannot_see_or_take(org, klass, make_user, login_as):
    lahore_principal = make_user("principal", Scope.BRANCH, org["lhr_franchise"])
    assert login_as(lahore_principal).get(url(klass["section"])).status_code == 404


def test_correction_is_audited_and_counts_update(org, klass, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    today = timezone.localdate()
    ids = [k.pk for k in klass["kids"]]
    save_register(klass["section"], today, {i: ("present", "") for i in ids}, klass["teacher"])
    save_register(klass["section"], today, {**{i: ("present", "") for i in ids}, ids[0]: ("late", "")}, principal)
    register = SectionAttendance.objects.get(section=klass["section"], date=today)
    assert (register.present, register.late, register.attended) == (2, 1, 3)
    event = AuditEvent.objects.get(model_label="attendance.AttendanceRecord")
    assert event.changes == {str(ids[0]): {"from": "present", "to": "late"}}
    assert event.actor == principal
    assert AttendanceRecord.objects.filter(date=today).count() == 3  # updated, not duplicated


def test_register_must_cover_the_whole_class(klass):
    with pytest.raises(ValueError):
        save_register(klass["section"], timezone.localdate(), {klass["kids"][0].pk: ("present", "")}, klass["teacher"])


def test_absentee_list_shows_parent_and_streak(org, klass, make_user, login_as):
    bilal = klass["kids"][1]
    others = {k.pk: ("present", "") for k in klass["kids"]}
    today = timezone.localdate()
    for back in (2, 1, 0):
        save_register(
            klass["section"], today - dt.timedelta(days=back), {**others, bilal.pk: ("absent", "")}, klass["teacher"]
        )
    assert absence_streaks([bilal.pk], today) == {bilal.pk: 3}
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    body = login_as(principal).get("/attendance/absent/").content.decode()
    assert "Bilal" in body and "03001112223" in body and "3 or more days" in body


def test_today_page_and_home_show_progress(org, klass, make_user, login_as):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    client = login_as(principal)
    assert "0/1" in client.get("/attendance/").content.decode()
    save_register(
        klass["section"], timezone.localdate(), {k.pk: ("present", "") for k in klass["kids"]}, klass["teacher"]
    )
    assert "1/1" in client.get("/attendance/").content.decode()
    assert "1/1" in client.get("/").content.decode()


def test_head_office_sees_branch_summary(org, klass, make_user, login_as):
    save_register(
        klass["section"], timezone.localdate(), {k.pk: ("present", "") for k in klass["kids"]}, klass["teacher"]
    )
    body = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])).get("/attendance/branches/").content
    body = body.decode()
    assert "Samanabad" in body and "100%" in body and "Test LHR Franchise" not in body


def test_accountant_cannot_take_register(org, klass, make_user, login_as):
    accountant = make_user("accountant", Scope.BRANCH, org["samanabad"])
    assert login_as(accountant).get("/attendance/").status_code == 403
