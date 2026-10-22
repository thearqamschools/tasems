"""The demo data command (for a test server with fictional data only)."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.admissions.models import Inquiry
from apps.attendance.models import SectionAttendance
from apps.diary.models import Diary
from apps.exams.models import Mark
from apps.fees.models import Payment, Voucher
from apps.hr.models import StaffDay
from apps.organisation.models import Branch
from apps.parents.models import ParentAccount
from apps.people.models import Student

pytestmark = pytest.mark.django_db


def test_demo_data_fills_an_empty_database(monkeypatch, settings):
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    call_command("seed_demo", verbosity=0)
    samanabad = Student.objects.filter(branch__code="fsd-samanabad")
    assert samanabad.count() == 32 + 6  # 6 in the demo Hifz section
    assert not Student.objects.exclude(reference="Demo data (fictional)").exists()
    assert all(s.admission_no.isdigit() for s in Student.objects.all())  # plain numbers, like the old software
    assert User.objects.get(username="demo-principal").check_password("Demo-pass-2026!")
    assert Diary.objects.filter(status="published").exists() and Mark.objects.exists()
    assert Voucher.objects.filter(branch__code="fsd-samanabad").count() == 32 and Payment.objects.exists()
    assert StaffDay.objects.exists() and Inquiry.objects.count() == 4 and ParentAccount.objects.count() == 1
    total = Student.objects.count()
    call_command("seed_demo", verbosity=0)  # safe to run again
    assert Student.objects.count() == total
    settings.DEMO_MODE = True
    assert not User.objects.get(username="demo-principal").requires_mfa


def test_demo_network_for_head_office(monkeypatch, client, settings):
    """Fictional branches under both head offices, each with registers and fees, and a network login."""
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    call_command("seed_demo", verbosity=0)
    demo = Branch.objects.filter(code__startswith="demo-")
    assert demo.count() == 6 and set(demo.values_list("head_office__code", flat=True)) == {"faisalabad", "lahore"}
    assert all("(DEMO)" in b.name and b.region_id for b in demo)
    assert SectionAttendance.objects.filter(section__branch__in=demo).exists()
    assert Payment.objects.filter(branch__in=demo).exists()
    settings.DEMO_MODE = True  # as on the demo server: no two-step sign-in
    network = User.objects.get(username="demo-network")
    assert network.accessible_branch_ids("people.view_student") == set(Branch.objects.values_list("id", flat=True))
    client.force_login(network)
    page = client.get("/").content.decode()
    assert "Demo Branch LHR-2" in page and "Demo Branch FSD-1" in page


def test_older_demo_gets_plain_numbers_and_usual_section_names(monkeypatch):
    from apps.academics.models import Section

    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    call_command("seed_demo", "--without-network", verbosity=0)
    for n, student in enumerate(Student.objects.order_by("pk"), start=1):  # as demos made before Oct 2026
        Student.objects.filter(pk=student.pk).update(admission_no=f"DEMO-{n:03d}", reference="")
    Section.objects.filter(name="Rose", class_level__code="class-4").update(name="A")
    call_command("seed_demo", "--without-network", verbosity=0)
    assert not Student.objects.filter(admission_no__startswith="DEMO-").exists()
    assert Student.objects.order_by("pk").first().admission_no == "4001"
    assert Section.objects.filter(class_level__code="class-4").get().name == "Rose"


def test_demo_refuses_a_database_with_real_students(org, students, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    with pytest.raises(CommandError):
        call_command("seed_demo", verbosity=0)
