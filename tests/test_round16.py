"""Round 16 (project lead, 24 Nov 2026): logos found on every computer, the exam's dates once at the top of Edit,
the date sheet page and PDF, the whole school's result, "Computer code", Marks & Results and the green button."""

from decimal import Decimal as D
from pathlib import PureWindowsPath

import pytest

from apps.core import paths
from apps.exams.models import Mark, Paper

from .test_exam_documents import exam_setup  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_file_addresses_work_with_spaces_and_windows_folders(tmp_path):
    folder = tmp_path / "Program Files" / "TASEMS"
    folder.mkdir(parents=True)
    assert paths.dir_uri(folder).startswith("file:///") and "Program%20Files/TASEMS/" in paths.dir_uri(folder)
    # What Path.as_uri gives on Windows (the old f"file://{folder}" did not make a valid address there).
    assert PureWindowsPath(r"C:\Program Files\TASEMS\static\fonts").as_uri() == (
        "file:///C:/Program%20Files/TASEMS/static/fonts"
    )
    assert paths.banner().startswith("data:image/png;base64,")  # the banner travels inside the page itself


def _all_marks(exam_setup):  # noqa: F811
    for student in exam_setup["kids"]:
        for paper in Paper.objects.filter(exam=exam_setup["exam"]):
            Mark.objects.create(
                branch=exam_setup["branch"], paper=paper, student=student, section=exam_setup["section"],
                obtained=D("30"), entered_by=exam_setup["principal"],
            )  # fmt: skip


def test_green_button_and_counts_and_names(exam_setup, login_as):  # noqa: F811
    client = login_as(exam_setup["principal"])
    page = client.get("/exams/").content.decode()
    assert "All classes & sections" in page and "Marks & Results" in page and "Marks & cards" not in page
    assert "button sm done" not in page
    a = exam_setup["kids"][0]
    Mark.objects.create(
        branch=exam_setup["branch"], paper=exam_setup["english"], student=a, section=exam_setup["section"],
        obtained=D("40"), entered_by=exam_setup["principal"],
    )  # fmt: skip
    assert "0 / 2" not in client.get("/exams/").content.decode()  # one paper of two: nobody complete yet
    Mark.objects.all().delete()
    _all_marks(exam_setup)
    page = client.get("/exams/").content.decode()
    assert "button sm done" in page  # every student, every paper: green


def test_marks_table_headings_and_result_card_column(exam_setup, login_as):  # noqa: F811
    client = login_as(exam_setup["principal"])
    page = client.get(f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/marks/").content.decode()
    assert "(50)" in page and "(100)" in page and "Result card" in page and "Comp. Code" in page
    assert ">Card<" not in page


def test_dates_once_at_the_top_and_whole_school_result(exam_setup, login_as, make_user):  # noqa: F811
    from apps.accounts.models import Scope

    _all_marks(exam_setup)
    exam = exam_setup["exam"]
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    page = admin.get(f"/exams/{exam.id}/papers/").content.decode()
    assert page.index("Exams start on") < page.index('class="class-tabs"') and "Save dates" in page
    client = login_as(exam_setup["principal"])
    results = client.get(f"/exams/{exam.id}/results/").content.decode()
    assert "Whole school" in results and "60%" in results  # 30 + 30 of 100 each
    sheet = client.get(f"/exams/{exam.id}/date-sheet/").content.decode()
    assert "arqam-banner" in sheet or "No dates set yet" in sheet
    card = client.get(f"/exams/{exam.id}/section/{exam_setup['section'].id}/result-cards.pdf")
    assert card.content[:4] == b"%PDF"
    student = client.get(f"/students/{exam_setup['kids'][0].id}/").content.decode()
    assert "Computer code" in student and "Admission no" not in student
