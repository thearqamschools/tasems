"""The seed must not make a second head-office campus when its code was changed in Setup → Branches
(project lead, 6 Nov 2026: after a restart the students and staff lists were empty, the top bar showed a new,
empty campus with the same name)."""

import datetime as dt

import pytest
from django.core.management import call_command

from apps.hr.models import Employee
from apps.organisation.models import Branch
from apps.people.models import Student

pytestmark = pytest.mark.django_db


def test_changed_code_does_not_make_a_second_campus(org):
    samanabad = org["samanabad"]
    Branch.objects.filter(pk=samanabad.pk).update(code="ho-faisalabad", name="Samanabad Head Office")
    Student.objects.create(branch=samanabad, admission_no="1", first_name="Ali", admission_date=dt.date(2026, 4, 1))
    before = Branch.objects.count()
    call_command("seed_tasems", verbosity=0)
    assert Branch.objects.count() == before
    samanabad.refresh_from_db()
    assert samanabad.code == "ho-faisalabad" and samanabad.name == "Samanabad Head Office"  # kept as changed


def test_empty_copy_made_by_the_old_seed_is_taken_out_of_use(org, login_as, make_user):
    from apps.accounts.models import Scope

    real = org["samanabad"]
    Branch.objects.filter(pk=real.pk).update(code="ho-faisalabad")
    copy = Branch.objects.create(code="fsd-samanabad", name=real.name, head_office=real.head_office,
                                 is_head_office=True, city="Faisalabad")  # fmt: skip
    Student.objects.create(branch=real, admission_no="1", first_name="Ali", admission_date=dt.date(2026, 4, 1))
    Employee.objects.create(branch=real, code="E1", full_name="Sana", gender="female", designation="Teacher",
                            staff_type="teaching", joined_on=dt.date(2025, 1, 1))  # fmt: skip
    call_command("seed_tasems", verbosity=0)
    copy.refresh_from_db()
    assert not copy.is_active and copy.code.startswith("unused-copy") and Branch.objects.filter(pk=real.pk).exists()
    assert Branch.objects.filter(name=real.name, is_active=True).count() == 1
    user = make_user("branch_owner", Scope.BRANCH, real)
    client = login_as(user)
    assert "Ali" in client.get("/students/").content.decode()
    assert "Sana" in client.get("/staff/").content.decode()


def test_copy_with_records_is_left_alone(org):
    real = org["samanabad"]
    Branch.objects.filter(pk=real.pk).update(code="ho-faisalabad")
    copy = Branch.objects.create(code="fsd-samanabad", name=real.name, head_office=real.head_office, city="Faisalabad")
    Student.objects.create(branch=copy, admission_no="9", first_name="Hina", admission_date=dt.date(2026, 4, 1))
    call_command("seed_tasems", verbosity=0)
    copy.refresh_from_db()
    assert copy.is_active and copy.code == "fsd-samanabad"
