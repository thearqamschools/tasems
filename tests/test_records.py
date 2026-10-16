"""Student records, enrolments, audit trail and admin screens."""

import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Role, Scope
from apps.core.models import AuditEvent
from apps.organisation.models import Branch, HeadOffice
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

pytestmark = pytest.mark.django_db


def test_seed_is_repeatable(seeded):
    call_command("seed_tasems", verbosity=0)
    assert HeadOffice.objects.count() == 2
    assert Branch.objects.get(code="fsd-samanabad").ownership == Branch.Ownership.COMPANY
    assert Role.objects.filter(is_system=True).count() == 11
    assert ClassLevel.objects.filter(stage="hifz").count() == 1


def test_franchise_default_royalty_is_8_percent(org):
    assert org["fsd_franchise"].royalty_percent == 8
    assert org["samanabad"].royalty_percent == 0


def test_admission_number_unique_within_branch_only(org, students):
    Student.objects.create(  # same number at another branch is fine
        branch=org["lhr_franchise"],
        admission_no="S-1",
        first_name="X",
        gender="female",
        admission_date=dt.date(2026, 4, 1),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Student.objects.create(
            branch=org["samanabad"],
            admission_no="S-1",
            first_name="Y",
            gender="male",
            admission_date=dt.date(2026, 4, 1),
        )


def test_enrolment_rejects_section_from_other_branch(org, students, section):
    enrolment = Enrolment(
        branch=org["fsd_franchise"], student=students["fsd_franchise"], session=org["session"], section=section
    )
    with pytest.raises(ValidationError):
        enrolment.full_clean()


def test_one_enrolment_per_session(org, students, section):
    s = students["samanabad"]
    Enrolment.objects.create(branch=s.branch, student=s, session=org["session"], section=section, roll_no=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Enrolment.objects.create(branch=s.branch, student=s, session=org["session"], section=section, roll_no=2)


def test_guardian_must_share_branch(org, students):
    guardian = Guardian.objects.create(branch=org["lhr_franchise"], full_name="Parent", phone="03000000000")
    link = StudentGuardian(student=students["samanabad"], guardian=guardian, relationship="father")
    with pytest.raises(ValidationError):
        link.full_clean()


def test_changes_are_audited_with_before_and_after(org, students):
    s = students["samanabad"]
    s.first_name = "Ahmad"
    s.save()
    event = AuditEvent.objects.filter(model_label="people.Student", object_id=str(s.pk), action="update").get()
    assert event.changes["first_name"] == {"from": "Student S-1", "to": "Ahmad"}
    assert event.branch_id == org["samanabad"].id


def test_passwords_never_reach_the_audit_log(make_user):
    user = make_user()
    for event in AuditEvent.objects.filter(model_label="accounts.User", object_id=str(user.pk)):
        assert "password" not in str(event.changes)


def test_admin_list_shows_only_own_branch(client, org, students, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"], is_staff=True)
    client.force_login(principal)
    response = client.get("/admin/people/student/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "S-1" in body
    assert "F-1" not in body and "L-1" not in body


def test_admin_hides_other_branch_record(client, org, students, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"], is_staff=True)
    client.force_login(principal)
    other = students["lhr_franchise"]
    response = client.get(f"/admin/people/student/{other.pk}/change/")
    assert response.status_code == 302  # redirected away: record is not visible to this user


def test_failed_login_is_audited(client, make_user):
    make_user()
    client.post("/admin/login/", {"username": "user1", "password": "wrong-password"})
    assert AuditEvent.objects.filter(action="login_failed").exists()


def test_section_name_unique_per_branch_session_class(org, section):
    with pytest.raises(IntegrityError), transaction.atomic():
        Section.objects.create(
            branch=org["samanabad"],
            session=org["session"],
            class_level=ClassLevel.objects.get(code="class-5"),
            name="A",
        )
