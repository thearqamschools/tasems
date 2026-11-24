"""Round 14 (project lead, 20–24 Nov 2026): a duty time for a day of the week, pay many employees at once, and the
year's four exams — papers, question papers, date sheet, marks of a section on one table, Excel in and out,
black-and-white result cards and progress."""

import datetime as dt
import io
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook

from apps.academics.models import Subject
from apps.accounts.models import Scope
from apps.exams.models import Exam, ExamRating, Mark, Paper
from apps.hr import services as S
from apps.hr.models import DutyTime, StaffDay
from apps.payroll.models import PayrollRun

from .test_exam_documents import exam_setup  # noqa: F401 (fixture)
from .test_round5 import OCT, payroll, school  # noqa: F401 (fixture)
from .test_round7 import punch, staff  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db

THU, FRI = dt.date(2026, 11, 5), dt.date(2026, 11, 6)


def test_friday_has_its_own_duty_times(staff, login_as):  # noqa: F811
    teacher = staff["person"]("E1", "Sana", machine_id="11")
    client = login_as(staff["director"])
    data = {"starts_from": "2026-11-02", "in_teaching": "08:00", "out_teaching": "14:00", "grace_teaching": "0",
            "pd_teaching_4_in": "07:30", "pd_teaching_4_out": "12:00"}  # fmt: skip
    client.post("/staff/attendance/times/", data)
    duty = DutyTime.objects.get(staff_type="teaching", starts_from=dt.date(2026, 11, 2))
    assert duty.per_day == {"4": {"in": "07:30", "out": "12:00"}}
    punch(teacher, THU, 7, 50, staff["director"])  # Thursday 08:00: on time
    punch(teacher, THU, 14, 5, staff["director"])
    punch(teacher, FRI, 7, 50, staff["director"])  # Friday 07:30: late
    punch(teacher, FRI, 12, 5, staff["director"])  # Friday Out 12:00: not early
    S.rebuild_days(staff["branch"], THU, FRI)
    thu, fri = (StaffDay.objects.get(employee=teacher, date=d) for d in (THU, FRI))
    assert thu.status == "present" and fri.status == "late" and not fri.early_left
    page = client.get("/staff/attendance/times/").content.decode()
    assert "A different time on a day of the week" in page and "Friday" in page


def test_pay_employees_marks_the_ticked_staff_as_paid(payroll, login_as):  # noqa: F811
    client = login_as(payroll["accountant"])
    assert "Finalise" in client.get(f"/payroll/pay/?month={OCT}", follow=True).content.decode()
    client.post(f"/payroll/finalise/?month={OCT}")
    run = PayrollRun.objects.get()
    page = client.get(f"/payroll/?month={OCT}").content.decode()
    assert "Pay employees" in page and page.index("Pay employees") < page.index("Acknowledgement sheet")
    pay = client.get(f"/payroll/pay/?month={OCT}").content.decode()
    t, g = (run.payslips.get(employee=payroll[k]) for k in ("teacher", "guard"))
    assert f'value="{t.id}"' in pay and "data-check-all" in pay
    client.post(f"/payroll/pay/?month={OCT}", {"paid_on": "2026-11-05", "use": [str(t.id)]})
    t.refresh_from_db()
    assert t.payment.amount == t.net_pay and t.payment.method == t.method
    assert not hasattr(run.payslips.get(pk=g.pk), "payment") or not run.payslips.filter(pk=g.pk, payment__isnull=False)
    left = client.get(f"/payroll/pay/?month={OCT}").content.decode()
    assert f'value="{t.id}"' not in left and f'value="{g.id}"' in left  # paid staff are not listed again


def test_four_exams_papers_question_paper_and_date_sheet(exam_setup, login_as, make_user):  # noqa: F811
    admin_user = make_user("network_admin", Scope.NETWORK)
    admin = login_as(admin_user)
    admin.post("/exams/add-session-exams/")
    kinds = sorted(Exam.objects.values_list("kind", flat=True))
    assert kinds == ["final", "mid", "pa1", "pa2"]
    index = admin.get("/exams/").content.decode()
    assert index.index("Periodic Assessment – I") < index.index("Mid-Term") < index.index("Periodic Assessment – II")
    pa2 = Exam.objects.get(kind="pa2")
    mid = Exam.objects.get(kind="mid")
    level = exam_setup["section"].class_level
    english, urdu = Subject.objects.get(code="english"), Subject.objects.get(code="urdu")
    summer = Subject.objects.get(code="summer-vacation-work")
    assert "Summer Vacation Work" in admin.get(f"/exams/{mid.id}/papers/?class={level.id}").content.decode()
    assert "Summer Vacation Work" not in admin.get(f"/exams/{pa2.id}/papers/?class={level.id}").content.decode()
    qp = SimpleUploadedFile("english.pdf", b"%PDF-1.4 question paper", content_type="application/pdf")
    totals = {f"total_{english.id}": "40", f"total_{urdu.id}": "40", f"total_{summer.id}": "10"}
    admin.post(f"/exams/{pa2.id}/papers/?class={level.id}", {**totals, f"qp_{english.id}": qp})
    papers = {p.subject.code: p for p in Paper.objects.filter(exam=pa2, class_level=level)}
    assert set(papers) == {"english", "urdu"} and papers["english"].question_paper  # no summer work outside Mid-Term
    admin.post(f"/exams/{mid.id}/papers/?class={level.id}", {"action": "copy", "source": pa2.id})
    assert Paper.objects.filter(exam=mid, class_level=level).count() == 2
    # The question paper is private until the exam day; the principal sees it, a class teacher does not.
    paper = papers["english"]
    paper.date = dt.date(2099, 1, 1)
    paper.save()
    teacher = make_user("class_teacher", Scope.BRANCH, exam_setup["branch"])
    assert login_as(teacher).get(f"/exams/question-paper/{paper.id}/").status_code == 403
    assert login_as(exam_setup["principal"]).get(f"/exams/question-paper/{paper.id}/").status_code == 200
    # Date sheet: first and last day, a day per paper, no times; PDF.
    admin = login_as(admin_user)  # the same test client: sign the admin in again
    admin.post(f"/exams/{pa2.id}/date-sheet/", {"starts_on": "2026-11-10", "ends_on": "2026-11-17",
                                                 f"date_{paper.id}": "2026-11-10"})  # fmt: skip
    page = admin.get(f"/exams/{pa2.id}/date-sheet/").content.decode()
    assert "10-11-26" in page and "17-11-26" in page and "English" in page
    pdf = admin.get(f"/exams/{pa2.id}/date-sheet.pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"


def test_marks_of_a_section_on_one_table_excel_cards_progress(exam_setup, login_as):  # noqa: F811
    exam, section, kids = exam_setup["exam"], exam_setup["section"], exam_setup["kids"]
    english = exam_setup["english"]
    urdu = Paper.objects.get(exam=exam, subject__code="urdu")
    client = login_as(exam_setup["principal"])
    url = f"/exams/{exam.id}/section/{section.id}/marks/"
    page = client.get(url).content.decode()
    assert "Slip0" in page and "English" in page and 'value="good" selected' in page
    a, b = kids
    bad = {f"m_{a.id}_{english.id}": "60", f"m_{a.id}_{urdu.id}": "40"}  # above the total of 50
    assert "need correcting" in client.post(url, bad, follow=True).content.decode()
    assert not Mark.objects.exists()
    client.post(url, {f"m_{a.id}_{english.id}": "45", f"m_{a.id}_{urdu.id}": "40.5", f"m_{b.id}_{english.id}": "A",
                      f"m_{b.id}_{urdu.id}": "30", f"r_{a.id}_attentive": "excellent"})  # fmt: skip
    assert Mark.objects.get(student=a, paper=english).obtained == D(45)
    assert Mark.objects.get(student=b, paper=english).status == "absent"
    r = ExamRating.objects.get(student=a, exam=exam)
    assert r.attentive == "excellent" and r.punctual == "good"
    # Excel out, changed, and back in: shown to check, saved only with Save.
    wb = load_workbook(io.BytesIO(client.get(f"{url}?format=xlsx").content))
    ws = wb["Marks"]
    assert ws.cell(4, 1).value in ("600", "601")
    row = 4 if ws.cell(4, 1).value == "601" else 5
    ws.cell(row, 3).value = 33  # b's English, column order: COMP.code, Name, English, Urdu (by date then name)
    buffer = io.BytesIO()
    wb.save(buffer)
    upload = SimpleUploadedFile("m.xlsx", buffer.getvalue())
    shown = client.post(url, {"action": "import", "file": upload}, follow=True).content.decode()
    assert "Check them and press Save marks" in shown and 'value="33"' in shown
    assert Mark.objects.get(student=b, paper=english).status == "absent"  # not saved yet
    printed = client.get(f"{url}?print=1").content.decode()
    assert "Marks sheet" in printed and "window.print()" in printed
    # Result cards: black and white, one per student; progress on the student's page.
    pdf = client.get(f"/exams/{exam.id}/section/{section.id}/result-cards.pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    one = client.get(f"/exams/{exam.id}/section/{section.id}/result-cards.pdf?student={a.id}")
    assert one.status_code == 200
    student_page = client.get(f"/students/{a.id}/").content.decode()
    assert "Exam results by year" in student_page and "85.50%" in student_page  # (45 + 40.5) / 100
    assert client.get("/exams/marks-reader-skill.zip")["Content-Type"] == "application/zip"
