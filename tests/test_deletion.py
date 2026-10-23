"""Deleting records made by mistake: who may, what goes with a record, and what stops it."""

import datetime as dt

import pytest

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope, User
from apps.core.models import AuditEvent
from apps.fees import services as fees
from apps.fees.models import FeeHead
from apps.organisation.models import AcademicSession, Branch, Campus
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(org, make_user):
    branch = org["samanabad"]
    section = Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="class-4"), name="Z"
    )
    kid = Student.objects.create(
        branch=branch, admission_no="9001", first_name="Mistake", gender="male", admission_date=dt.date(2026, 4, 1)
    )
    Enrolment.objects.create(branch=branch, student=kid, session=org["session"], section=section)
    return {
        "branch": branch,
        "section": section,
        "kid": kid,
        "director": make_user("branch_owner", Scope.BRANCH, branch),
    }


def test_director_deletes_a_student_added_by_mistake(school, login_as):
    client = login_as(school["director"])
    url = f"/delete/student/{school['kid'].id}/"
    page = client.get(url).content.decode()
    assert "Delete this student?" in page and "Mistake" in page and "enrolment" in page.lower()
    assert Student.objects.filter(pk=school["kid"].pk).exists()  # looking changes nothing
    assert "Give a reason" in client.post(url, {"reason": ""}).content.decode()
    done = client.post(url, {"reason": "Added twice"})
    assert done.status_code == 302 and done.url == "/students/"
    assert not Student.objects.filter(pk=school["kid"].pk).exists() and not Enrolment.objects.exists()
    event = AuditEvent.objects.filter(action="delete", model_label="people.Student").latest("occurred_at")
    assert event.changes["reason"] == "Added twice" and event.actor == school["director"]


def test_records_with_history_are_kept(school, login_as):
    fees.add_charge(school["kid"], FeeHead.objects.get(code="others"), dt.date(2026, 10, 1), 500, school["director"])
    client = login_as(school["director"])
    page = client.get(f"/delete/student/{school['kid'].id}/").content.decode()
    assert "cannot be deleted" in page and "charge" in page.lower()
    client.post(f"/delete/student/{school['kid'].id}/", {"reason": "x"})
    assert Student.objects.filter(pk=school["kid"].pk).exists()
    section_page = client.get(f"/delete/section/{school['section'].id}/").content.decode()
    assert "cannot be deleted" in section_page  # a student is placed in it


def test_who_may_delete(school, login_as, make_user, org):
    principal = login_as(make_user("principal", Scope.BRANCH, school["branch"]))
    assert principal.get(f"/delete/student/{school['kid'].id}/").status_code == 403
    assert "/delete/student/" not in principal.get(f"/students/{school['kid'].id}/").content.decode()
    director = login_as(school["director"])
    assert "/delete/student/" in director.get(f"/students/{school['kid'].id}/").content.decode()
    other = login_as(make_user("branch_owner", Scope.BRANCH, org["fsd_franchise"]))
    assert other.get(f"/delete/student/{school['kid'].id}/").status_code in (403, 404)  # another branch
    # A Director cannot delete the branch itself or network lists.
    assert director.get(f"/delete/branch/{school['branch'].id}/").status_code == 403
    assert director.get(f"/delete/session/{org['session'].id}/").status_code == 403


def test_head_office_and_master_login(school, login_as, make_user, org):
    spare = Branch.objects.create(code="oops", name="Made by mistake", head_office=org["fsd"], city="Faisalabad")
    Campus.objects.create(branch=spare, name="Main")
    office = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"]))
    assert office.get(f"/delete/branch/{org['lhr_franchise'].id}/").status_code == 403  # the other head office
    assert "/delete/branch/" in office.get(f"/setup/branches/{spare.id}/").content.decode()
    office.post(f"/delete/branch/{spare.id}/", {"reason": "Made by mistake"})
    assert not Branch.objects.filter(pk=spare.pk).exists()  # with its empty campus
    busy = office.get(f"/delete/branch/{school['branch'].id}/").content.decode()
    assert "cannot be deleted" in busy
    assert office.get(f"/delete/session/{org['session'].id}/").status_code == 403  # network-wide list
    spare_session = AcademicSession.objects.create(
        name="2030-31", starts_on=dt.date(2030, 4, 1), ends_on=dt.date(2031, 3, 31)
    )
    master = User.objects.create_superuser("master", password="Str0ng-pass-123")
    client = login_as(master)
    client.post(f"/delete/session/{spare_session.id}/", {"reason": "Wrong year"})
    assert not AcademicSession.objects.filter(pk=spare_session.pk).exists()
    assert client.get(f"/delete/user/{master.id}/").status_code == 403  # never oneself


def test_logins_are_deleted_only_within_reach(org, login_as, make_user):
    office = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    teacher = make_user("class_teacher", Scope.BRANCH, org["fsd_franchise"])
    far = make_user("class_teacher", Scope.BRANCH, org["lhr_franchise"])
    client = login_as(office)
    assert client.get(f"/delete/user/{far.id}/").status_code in (403, 404)
    client.post(f"/delete/user/{teacher.id}/", {"reason": "Wrong person"})
    assert not User.objects.filter(pk=teacher.pk).exists()
