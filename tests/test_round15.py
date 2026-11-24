"""Round 15 (project lead, 24 Nov 2026): branch details, classes & subjects, one Edit page for an exam, the date sheet
and result card with the school's banner and fonts, ADM.NO. on the marks table, result reports with pass at 33% and
positions, and the progress report."""

import datetime as dt
from decimal import Decimal as D

import pytest

from apps.academics.models import CurriculumSubject, Subject
from apps.accounts.models import Scope
from apps.exams import reports
from apps.exams.documents import branch_address
from apps.exams.models import Mark, Paper

from .test_exam_documents import exam_setup  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_branch_details_with_website_and_address_on_papers(exam_setup, login_as, make_user):  # noqa: F811
    branch = exam_setup["branch"]
    owner = make_user("branch_owner", Scope.BRANCH, branch)
    client = login_as(owner)
    assert "Branch details" in client.get("/setup/").content.decode()
    client.post("/setup/branch-details/", {"name": branch.name, "address": "Sanora Colony,\nSamanabad, Faisalabad",
                                           "phone": "041-2660265", "mobile_1": "0339-2406479",
                                           "website": "www.thearqam.com"})  # fmt: skip
    branch.refresh_from_db()
    assert branch.website == "www.thearqam.com" and branch.mobile_1 == "0339-2406479"
    assert branch_address(branch) == "Sanora Colony, Samanabad, Faisalabad"  # one line, no "Head Office"


def test_class_subjects_decide_the_exam_subjects(exam_setup, login_as, make_user):  # noqa: F811
    admin_user = make_user("network_admin", Scope.NETWORK)
    client = login_as(admin_user)
    level = exam_setup["section"].class_level
    english, urdu = Subject.objects.get(code="english"), Subject.objects.get(code="urdu")
    client.post(f"/setup/classes-subjects/?class={level.id}", {"subject": [english.id, urdu.id]})
    assert set(CurriculumSubject.objects.filter(class_level=level).values_list("subject__code", flat=True)) == {
        "english",
        "urdu",
    }
    client.post(f"/setup/classes-subjects/?class={level.id}", {"action": "add_subject", "name": "Tarjama tul Quran"})
    assert CurriculumSubject.objects.filter(class_level=level, subject__name="Tarjama tul Quran").exists()
    exam = exam_setup["exam"]  # the Mid-Term
    page = client.get(f"/exams/{exam.id}/papers/?class={level.id}").content.decode()
    assert "Tarjama tul Quran" in page and "Summer Vacation Work" in page and "Mathematics" not in page
    assert "Generate date sheet (PDF)" in page and "Exams start on" in page
    # One page: first and last day, total marks and each paper's day saved together (R15-4).
    client.post(f"/exams/{exam.id}/papers/?class={level.id}", {
        "starts_on": "2026-11-10", "ends_on": "2026-11-17", f"total_{english.id}": "40",
        f"date_{english.id}": "2026-11-10", f"total_{urdu.id}": "40", f"date_{urdu.id}": "2026-11-11"})  # fmt: skip
    exam.refresh_from_db()
    paper = Paper.objects.get(exam=exam, class_level=level, subject=english)
    assert (exam.starts_on, exam.ends_on, paper.total_marks, paper.date) == (
        dt.date(2026, 11, 10),
        dt.date(2026, 11, 17),
        40,
        dt.date(2026, 11, 10),
    )
    index = client.get("/exams/").content.decode()
    assert f"/exams/{exam.id}/papers/" in index and f"/exams/{exam.id}/results/" in index and ">Edit<" in index
    pdf = client.get(f"/exams/{exam.id}/date-sheet.pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"


def _marks(exam_setup, a_marks, b_marks):  # noqa: F811
    a, b = exam_setup["kids"]
    papers = list(Paper.objects.filter(exam=exam_setup["exam"]).order_by("subject__name"))
    for student, values in ((a, a_marks), (b, b_marks)):
        for paper, value in zip(papers, values, strict=True):
            Mark.objects.create(
                branch=exam_setup["branch"], paper=paper, student=student, section=exam_setup["section"],
                obtained=D(value), entered_by=exam_setup["principal"],
            )  # fmt: skip


def test_marks_table_shows_admission_number_not_roll(exam_setup, login_as):  # noqa: F811
    client = login_as(exam_setup["principal"])
    page = client.get(f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/marks/").content.decode()
    assert "ADM.NO." in page and ">Roll<" not in page and ">600<" in page


def test_result_report_pass_at_33_and_positions(exam_setup, login_as):  # noqa: F811
    _marks(exam_setup, ["40", "45"], ["10", "12"])  # English, Urdu out of 50 each: 85% and 22%
    exam, section = exam_setup["exam"], exam_setup["section"]
    result = reports.class_result(exam, [section])
    first, second = result["students"]
    assert first["position"] == 1 and first["passed"] and first["percent"] == D("85.00")
    assert second["position"] == 2 and not second["passed"]
    assert result["summary"]["passed"] == 1 and result["summary"]["failed"] == 1
    assert {r["subject"].name: r["average"] for r in result["subjects"]}["English"] == D("50.00")
    client = login_as(exam_setup["principal"])
    page = client.get(f"/exams/{exam.id}/results/?class={section.class_level_id}").content.decode()
    assert "1st" in page and "2nd" in page and "Fail" in page and "Students by percentage" in page
    overview = client.get(f"/exams/{exam.id}/results/").content.decode()
    assert "All classes" in overview and str(section.class_level) in overview
    pdf = client.get(f"/exams/{exam.id}/results/?class={section.class_level_id}&format=pdf")
    assert pdf["Content-Type"] == "application/pdf"
    xlsx = client.get(f"/exams/{exam.id}/results/?class={section.class_level_id}&format=xlsx")
    assert xlsx.status_code == 200
    # Equal percentages share a position.
    ranked = reports.rank([{"percent": D("90")}, {"percent": D("90")}, {"percent": D("70")}])
    assert [r["position"] for r in ranked] == [1, 1, 3]


def test_progress_report_and_card(exam_setup, login_as):  # noqa: F811
    _marks(exam_setup, ["40", "45"], ["10", "12"])
    a = exam_setup["kids"][0]
    client = login_as(exam_setup["principal"])
    page = client.get(f"/exams/progress/{a.id}/").content.decode()
    assert "PROGRESS REPORT" in page and "85.00%" in page and "Pass" in page
    assert "Progress report (this session)" in client.get(f"/students/{a.id}/").content.decode()
    card = client.get(f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/result-cards.pdf")
    assert card["Content-Type"] == "application/pdf" and card.content[:4] == b"%PDF"
