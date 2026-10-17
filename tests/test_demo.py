"""The demo data command (for a test server with fictional data only)."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.admissions.models import Inquiry
from apps.diary.models import Diary
from apps.exams.models import Mark
from apps.fees.models import Payment, Voucher
from apps.hr.models import StaffDay
from apps.parents.models import ParentAccount
from apps.people.models import Student

pytestmark = pytest.mark.django_db


def test_demo_data_fills_an_empty_database(monkeypatch, settings):
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    call_command("seed_demo", verbosity=0)
    assert Student.objects.count() == 32 and not Student.objects.exclude(admission_no__startswith="DEMO-").exists()
    assert User.objects.get(username="demo-principal").check_password("Demo-pass-2026!")
    assert Diary.objects.filter(status="published").exists() and Mark.objects.exists()
    assert Voucher.objects.count() == 32 and Payment.objects.exists()
    assert StaffDay.objects.exists() and Inquiry.objects.count() == 4 and ParentAccount.objects.count() == 1
    call_command("seed_demo", verbosity=0)  # safe to run again
    assert Student.objects.count() == 32
    settings.DEMO_MODE = True
    assert not User.objects.get(username="demo-principal").requires_mfa


def test_demo_refuses_a_database_with_real_students(org, students, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    with pytest.raises(CommandError):
        call_command("seed_demo", verbosity=0)
