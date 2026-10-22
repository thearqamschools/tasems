"""M7: date sheet, exam slips with photo and award lists."""

import datetime as dt

import pytest

from apps.academics.models import ClassLevel, Section, Subject
from apps.accounts.models import Scope
from apps.exams.models import Exam, Mark, Paper
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db


@pytest.fixture
def exam_setup(org, make_user):
    branch, session = org["samanabad"], org["session"]
    level = ClassLevel.objects.get(code="class-4")
    section = Section.objects.create(branch=branch, session=session, class_level=level, name="Rose")
    exam = Exam.objects.create(session=session, kind="mid", name="Mid-Term Examination 2026-27")
    english = Paper.objects.create(
        exam=exam, class_level=level, subject=Subject.objects.get(code="english"), total_marks=50
    )
    Paper.objects.create(exam=exam, class_level=level, subject=Subject.objects.get(code="urdu"), total_marks=50)
    kids = []
    for n in range(2):
        s = Student.objects.create(
            branch=branch,
            admission_no=str(600 + n),
            first_name=f"Slip{n}",
            father_name="F",
            gender="male",
            admission_date=dt.date(2026, 4, 1),
        )
        Enrolment.objects.create(branch=branch, student=s, session=session, section=section, roll_no=n + 1)
        kids.append(s)
    principal = make_user("principal", Scope.BRANCH, branch)
    return {
        "branch": branch,
        "section": section,
        "exam": exam,
        "english": english,
        "kids": kids,
        "principal": principal,
    }


def test_network_date_sheet_is_set_by_network_exam_setup_only(exam_setup, login_as, make_user):
    exam, english = exam_setup["exam"], exam_setup["english"]
    principal = login_as(exam_setup["principal"])
    page = principal.get(f"/exams/{exam.id}/date-sheet/").content.decode()
    assert "English" in page and "Change dates and times" not in page
    assert principal.post(f"/exams/{exam.id}/date-sheet/", {f"date_{english.id}": "2026-11-02"}).status_code == 403
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    admin.post(
        f"/exams/{exam.id}/date-sheet/",
        {f"date_{english.id}": "2026-11-02", f"starts_at_{english.id}": "08:30", f"ends_at_{english.id}": "10:30"},
    )
    english.refresh_from_db()
    assert (english.date, english.starts_at) == (dt.date(2026, 11, 2), dt.time(8, 30))


def test_branch_exam_date_sheet_by_branch_setup(exam_setup):
    from apps.exams.documents import can_edit_date_sheet

    exam = exam_setup["exam"]
    exam.branch = exam_setup["branch"]
    assert not can_edit_date_sheet(exam_setup["principal"], exam, exam_setup["branch"])  # principals do not set papers


def test_exam_slips_pdf_for_a_section_or_one_student(exam_setup, login_as):
    client = login_as(exam_setup["principal"])
    url = f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/slips/"
    pdf = client.get(url)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    one = client.get(f"{url}?student={exam_setup['kids'][0].id}")
    assert one.status_code == 200
    assert (
        "Exam slips (PDF)"
        in client.get(f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/").content.decode()
    )


def test_award_list_shows_entered_marks_and_blanks(exam_setup, login_as):
    english, section = exam_setup["english"], exam_setup["section"]
    Mark.objects.create(
        branch=exam_setup["branch"],
        paper=english,
        student=exam_setup["kids"][0],
        section=section,
        obtained=41,
        entered_by=exam_setup["principal"],
    )
    client = login_as(exam_setup["principal"])
    page = client.get(f"/exams/paper/{english.id}/section/{section.id}/award-list/").content.decode()
    assert "Award list" in page and "Slip0" in page and "Slip1" in page and ">41<" in page.replace(" ", "")
    xlsx = client.get(f"/exams/paper/{english.id}/section/{section.id}/award-list/?format=xlsx")
    assert xlsx.status_code == 200
