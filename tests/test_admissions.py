"""Admissions: inquiries, follow-ups, conversion to a student, and reports."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.admissions import services as S
from apps.admissions.models import FollowUp, Inquiry
from apps.people.models import Guardian, Student, StudentGuardian

pytestmark = pytest.mark.django_db


@pytest.fixture
def adm(org, make_user):
    branch = org["samanabad"]
    officer = make_user("admissions_officer", Scope.BRANCH, branch)
    Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="play-group"), name="Tulip"
    )
    return {"branch": branch, "officer": officer, "level": ClassLevel.objects.get(code="play-group")}


def post_inquiry(client, adm, **extra):
    data = {
        "child_name": "Ahmar Rauf",
        "gender": "male",
        "class_level": adm["level"].id,
        "parent_name": "Abdul Rauf",
        "phone": "0300-1234567",
        "source": "facebook",
    }
    data.update(extra)
    return client.post("/admissions/new/", data)


def test_quick_inquiry_and_follow_up(adm, login_as):
    client = login_as(adm["officer"])
    response = post_inquiry(client, adm)
    inquiry = Inquiry.objects.get()
    assert response.url == f"/admissions/{inquiry.id}/"
    assert inquiry.phone == "03001234567" and inquiry.status == "new" and inquiry.assigned_to == adm["officer"]
    assert inquiry.next_follow_up == timezone.localdate() + dt.timedelta(days=1)
    page = client.get(response.url).content.decode()
    assert "https://wa.me/923001234567?text=" in page
    visit = (timezone.localdate() + dt.timedelta(days=3)).isoformat()
    client.post(
        response.url,
        {
            "kind": "call",
            "note": "Will visit on Saturday",
            "status": "visit",
            "visit_at": f"{visit}T10:30",
            "next_follow_up": visit,
        },
    )
    inquiry.refresh_from_db()
    assert inquiry.status == "visit" and inquiry.visit_at is not None
    assert list(inquiry.follow_ups.values_list("kind", flat=True)) == ["status", "call", "note"]


def test_lost_needs_a_reason(adm, login_as):
    client = login_as(adm["officer"])
    url = post_inquiry(client, adm).url
    body = client.post(url, {"kind": "call", "note": "Too far", "status": "lost"}).content.decode()
    assert "Choose why" in body
    client.post(url, {"kind": "call", "note": "Too far", "status": "lost", "lost_reason": "distance"})
    inquiry = Inquiry.objects.get()
    assert inquiry.status == "lost" and inquiry.next_follow_up is None and inquiry.closed_on == timezone.localdate()


def test_siblings_at_school_are_shown(adm, login_as):
    g = Guardian.objects.create(branch=adm["branch"], full_name="Abdul Rauf", phone="03001234567")
    s = Student.objects.create(
        branch=adm["branch"], admission_no="X-1", first_name="Elder", gender="male", admission_date=dt.date(2025, 4, 1)
    )
    StudentGuardian.objects.create(student=s, guardian=g, relationship="father", is_primary_contact=True)
    client = login_as(adm["officer"])
    url = post_inquiry(client, adm).url
    assert "Elder" in client.get(url).content.decode()


def test_admit_makes_the_student(adm, login_as, org):
    client = login_as(adm["officer"])
    url = post_inquiry(client, adm).url
    inquiry = Inquiry.objects.get()
    section = Section.objects.get(name="Tulip")
    response = client.post(
        f"{url}admit/",
        {
            "admission_no": "PG-101",
            "first_name": "Ahmar",
            "last_name": "Rauf",
            "gender": "male",
            "admission_date": timezone.localdate().isoformat(),
            "guardian_name": "Abdul Rauf",
            "guardian_phone": "0300-1234567",
            "relationship": "father",
            "section": section.id,
        },
    )
    inquiry.refresh_from_db()
    student = Student.objects.get(admission_no="PG-101")
    assert inquiry.student == student and inquiry.status == "admitted"
    assert student.enrolments.get().section == section
    assert response.url == f"/fees/student/{student.id}/voucher/"  # admission voucher next


def test_due_list_report_and_excel(adm, login_as):
    client = login_as(adm["officer"])
    post_inquiry(client, adm)
    post_inquiry(client, adm, child_name="Hira", gender="female", source="walk_in", phone="0311-2223334")
    Inquiry.objects.update(next_follow_up=timezone.localdate())
    assert len(S.due(adm["branch"])) == 2
    page = client.get("/admissions/?view=due").content.decode()
    assert "Ahmar Rauf" in page and "Hira" in page
    report = S.report(adm["branch"], timezone.localdate() - dt.timedelta(days=1), timezone.localdate())
    assert report["total"] == 2 and {s for s, _n, _w in report["by_source"]} == {"Facebook", "Walk-in"}
    sheet = client.get("/admissions/?view=all&format=xlsx")
    assert sheet["Content-Type"].startswith("application/vnd.openxml")
    assert client.get("/admissions/report/").status_code == 200


def test_access(adm, org, login_as, make_user):
    client = login_as(adm["officer"])
    post_inquiry(client, adm)
    inquiry = Inquiry.objects.get()
    assert login_as(make_user("class_teacher", Scope.BRANCH, adm["branch"])).get("/admissions/").status_code == 403
    other = login_as(make_user("principal", Scope.BRANCH, org["fsd_franchise"]))
    assert other.get(f"/admissions/{inquiry.id}/").status_code == 404
    assert FollowUp.objects.count() == 1
