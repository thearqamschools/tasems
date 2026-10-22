"""M6: large PDFs are made in the background and only the person who asked can download them."""

import datetime as dt

import pytest
from django.core.management import call_command

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.fees import services as S
from apps.fees import views as fee_views
from apps.jobs import runner
from apps.jobs.models import Job
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db
OCT = dt.date(2026, 10, 1)


@pytest.fixture
def setup(org, make_user, settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr(fee_views, "MAX_PRINT", 2)  # three vouchers count as "large" here
    branch, session = org["samanabad"], org["session"]
    section = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    for n in range(3):
        s = Student.objects.create(
            branch=branch,
            admission_no=str(800 + n),
            first_name=f"Pupil{n}",
            father_cnic="3310033333333" if n < 2 else "",
            gender="male",
            admission_date=dt.date(2024 + n, 4, 1),
        )
        Enrolment.objects.create(branch=branch, student=s, session=session, section=section)
    accountant = make_user("accountant", Scope.BRANCH, branch)
    S.generate_vouchers(branch, session, OCT, OCT, dt.date(2026, 10, 10), accountant)
    return {"branch": branch, "accountant": accountant}


def test_large_voucher_print_runs_in_the_background(setup, login_as, make_user):
    client = login_as(setup["accountant"])
    queued = client.get("/fees/vouchers/print/?month=2026-10")
    job = Job.objects.get()
    assert queued.status_code == 302 and queued.url == f"/print-jobs/{job.id}/"
    page = client.get(queued.url).content.decode()
    assert "Waiting" in page and 'http-equiv="refresh"' in page
    call_command("run_jobs", "--once")
    job.refresh_from_db()
    assert job.status == Job.Status.DONE and (job.done, job.total) == (3, 3)
    pdf = client.get(f"/print-jobs/{job.id}/download/")
    assert pdf.status_code == 200 and b"".join(pdf.streaming_content).startswith(b"%PDF")
    assert "My print jobs" in client.get("/print-jobs/").content.decode()
    someone_else = login_as(make_user("principal", Scope.BRANCH, setup["branch"]))
    assert someone_else.get(f"/print-jobs/{job.id}/download/").status_code == 404


def test_small_print_is_immediate(setup, login_as, monkeypatch):
    monkeypatch.setattr(fee_views, "MAX_PRINT", 100)
    direct = login_as(setup["accountant"]).get("/fees/vouchers/print/?month=2026-10")
    assert direct.status_code == 200 and direct.content.startswith(b"%PDF") and not Job.objects.exists()


def test_a_job_that_cannot_be_made_says_why(setup):
    job = Job.objects.create(
        branch=setup["branch"],
        kind="vouchers",
        title="Nothing",
        params={"query": "month=2030-01"},
        requested_by=setup["accountant"],
    )
    runner.run_one()
    job.refresh_from_db()
    assert job.status == Job.Status.FAILED and "No vouchers" in job.error


def test_old_jobs_are_cleaned_and_stuck_ones_requeued(setup):
    job = Job.objects.create(
        branch=setup["branch"],
        kind="vouchers",
        title="Old",
        status=Job.Status.RUNNING,
        requested_by=setup["accountant"],
    )
    Job.objects.filter(pk=job.pk).update(
        updated_at=job.updated_at - dt.timedelta(hours=1), created_at=job.created_at - dt.timedelta(days=8)
    )
    assert runner.requeue_stuck() == 1
    assert runner.clean_old() == 1 and not Job.objects.exists()


def test_family_vouchers_print_in_the_background(setup, login_as, monkeypatch):
    from apps.fees import family

    monkeypatch.setattr(fee_views, "MAX_PRINT", 0)
    family.make(setup["branch"], OCT, setup["accountant"])
    client = login_as(setup["accountant"])
    queued = client.get("/fees/family/print/?month=2026-10")
    job = Job.objects.get(kind="family_vouchers")
    assert queued.url == f"/print-jobs/{job.id}/"
    runner.run_one()
    job.refresh_from_db()
    assert job.status == Job.Status.DONE and job.file.read().startswith(b"%PDF")
