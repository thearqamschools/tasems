"""Parent portal: set-up with a school code, sign-in, and seeing only one's own children."""

import datetime as dt
import re
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.attendance.models import AttendanceRecord
from apps.diary.models import Diary
from apps.fees import services as fees
from apps.fees.models import FeeHead
from apps.parents import services as S
from apps.parents.models import AccessCode, ParentAccount
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

pytestmark = pytest.mark.django_db
PHONE = "03001234567"
PASSWORD = "Strong-family-pass-26"


@pytest.fixture
def family(org, make_user):
    branch = org["samanabad"]
    principal = make_user("principal", Scope.BRANCH, branch)
    section = Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="class-4"), name="A"
    )
    guardian = Guardian.objects.create(branch=branch, full_name="Abdul Rauf", phone=PHONE)
    kids = []
    for n, name in enumerate(["Ahmad", "Hira"], 1):
        s = Student.objects.create(
            branch=branch, admission_no=f"P-{n}", first_name=name, gender="male", admission_date=dt.date(2026, 4, 1)
        )
        Enrolment.objects.create(branch=branch, student=s, session=org["session"], section=section)
        StudentGuardian.objects.create(student=s, guardian=guardian, relationship="father", is_primary_contact=True)
        kids.append(s)
    other_guardian = Guardian.objects.create(branch=branch, full_name="Someone Else", phone="03119998887")
    stranger = Student.objects.create(
        branch=branch, admission_no="P-9", first_name="Stranger", gender="male", admission_date=dt.date(2026, 4, 1)
    )
    StudentGuardian.objects.create(
        student=stranger, guardian=other_guardian, relationship="father", is_primary_contact=True
    )
    return {"branch": branch, "principal": principal, "section": section, "kids": kids, "stranger": stranger}


def slip_code(response):
    match = re.search(r'class="code">(\d{4}) (\d{4})<', response.content.decode())
    return match.group(1) + match.group(2)


def set_up(client, login_as, family):
    staff = login_as(family["principal"])
    page = staff.post("/parents/codes/", {"student": family["kids"][0].id})
    code = slip_code(page)
    staff.logout()
    client.post(
        "/parents/start/",
        {"phone": "0300-1234567", "code": code, "password1": PASSWORD, "password2": PASSWORD},
    )
    return code


def test_school_code_sets_up_the_account(client, login_as, family):
    code = set_up(client, login_as, family)
    account = ParentAccount.objects.get(phone=PHONE)
    assert account.user.check_password(PASSWORD)
    assert AccessCode.objects.get(phone=PHONE).used_at is not None
    home = client.get("/parents/").content.decode()
    assert "Ahmad" in home and "Hira" in home and "Stranger" not in home
    # the code works only once
    client.post("/parents/logout/")
    again = client.post(
        "/parents/start/", {"phone": PHONE, "code": code, "password1": PASSWORD, "password2": PASSWORD}
    ).content.decode()
    assert "not correct or has expired" in again


def test_sign_in_and_lockout(client, login_as, family):
    set_up(client, login_as, family)
    client.post("/parents/logout/")
    assert client.post("/parents/login/", {"phone": PHONE, "password": PASSWORD}).status_code == 302
    client.post("/parents/logout/")
    for _ in range(5):
        client.post("/parents/login/", {"phone": PHONE, "password": "wrong-password-1"})
    body = client.post("/parents/login/", {"phone": PHONE, "password": PASSWORD}).content.decode()
    assert "Too many failed attempts" in body


def test_parent_sees_only_own_children(client, login_as, family):
    set_up(client, login_as, family)
    ahmad, stranger = family["kids"][0], family["stranger"]
    assert client.get(f"/parents/child/{ahmad.id}/?tab=attendance").status_code == 200
    assert client.get(f"/parents/child/{stranger.id}/").status_code == 404
    assert client.get("/students/").status_code == 403  # no staff screens
    assert client.get("/").url == "/parents/"


def test_child_tabs_show_diary_attendance_fees(client, login_as, family):
    set_up(client, login_as, family)
    ahmad = family["kids"][0]
    today = timezone.localdate()
    AttendanceRecord.objects.create(
        branch=family["branch"],
        student=ahmad,
        section=family["section"],
        date=today,
        status="absent",
        marked_by=family["principal"],
    )
    assert "Absent" in client.get(f"/parents/child/{ahmad.id}/?tab=attendance").content.decode()
    Diary.objects.create(
        branch=family["branch"],
        section=family["section"],
        date=today,
        status="published",
        written_by=family["principal"],
    )
    page = client.get(f"/parents/child/{ahmad.id}/").content.decode()
    assert "Open as PDF" in page
    diary = Diary.objects.get(section=family["section"], date=today)
    image = client.get(f"/parents/child/{ahmad.id}/diary/{diary.id}.png")
    assert image.status_code == 200 and image["Content-Type"] == "image/png"
    fees.add_charge(ahmad, FeeHead.objects.get(code="others"), today, Decimal("500"), family["principal"], note="Books")
    assert "500" in client.get(f"/parents/child/{ahmad.id}/?tab=fees").content.decode()


def test_teacher_cannot_issue_codes(client, login_as, family, make_user):
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, family["branch"]))
    assert teacher.post("/parents/codes/", {"student": family["kids"][0].id}).status_code == 403


def test_new_code_replaces_old_one(family):
    first = S.issue_code(PHONE, family["branch"], family["principal"])
    second = S.issue_code(PHONE, family["branch"], family["principal"])
    assert S.check_code(PHONE, first) is None and S.check_code(PHONE, second) is not None
