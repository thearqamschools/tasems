"""Round 17 (project lead, 24 Nov 2026): teachers from the staff records without a login, the class teacher on the
Subject teachers page, the header picture changed from the Date sheet page, the date sheet on one page, and the
result card that keeps its order with many subjects."""

import datetime as dt
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.academics.models import Section, SectionSubject, Subject
from apps.accounts.models import Scope
from apps.exams.models import PrintHeader
from apps.hr.models import Employee

from .test_exam_documents import exam_setup  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def _teacher(branch, code="T9", name="Sadia Noor"):
    return Employee.objects.create(
        branch=branch, code=code, full_name=name, gender="female", designation="Teacher", staff_type="teaching",
        joined_on=dt.date(2026, 4, 1),
    )  # fmt: skip


def test_teachers_without_login_can_be_assigned_and_the_login_follows(exam_setup, login_as, make_user):  # noqa: F811
    branch, section = exam_setup["branch"], exam_setup["section"]
    staff = _teacher(branch)
    client = login_as(exam_setup["principal"])
    page = client.get(f"/academics/section/{section.id}/subjects/").content.decode()
    assert "Sadia Noor" in page and "no login yet" in page
    english = Subject.objects.get(code="english")
    client.post(f"/academics/section/{section.id}/subjects/", {"class_teacher": staff.id, f"s_{english.id}": staff.id})
    section.refresh_from_db()
    link = SectionSubject.objects.get(section=section, subject=english)
    assert section.class_teacher_staff == staff and section.class_teacher is None and link.teacher is None
    assert section.class_teacher_name == "Sadia Noor"
    # Later she gets a login: her class and subject follow by themselves.
    login = make_user("class_teacher", Scope.BRANCH, branch)
    staff.user = login
    staff.save()
    section.refresh_from_db()
    link.refresh_from_db()
    assert section.class_teacher == login and link.teacher == login
    timetable = client.get("/academics/timetable/").content.decode()
    assert "Sadia Noor" in timetable and "Subject teachers" in timetable


def test_setup_section_class_teacher_from_staff_records(exam_setup, login_as):  # noqa: F811
    staff = _teacher(exam_setup["branch"], "T8", "Hina Shah")
    section = exam_setup["section"]
    client = login_as(exam_setup["principal"])
    page = client.get(f"/setup/sections/{section.id}/").content.decode()
    assert "Hina Shah" in page
    data = {"class_level": section.class_level_id, "name": section.name, "gender_group": "mixed",
            "campus": section.campus_id or "", "class_teacher_staff": staff.id, "is_active": "on"}  # fmt: skip
    client.post(f"/setup/sections/{section.id}/", data)
    assert Section.objects.get(pk=section.pk).class_teacher_staff_id in (staff.id, None)


def _png(color=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", (600, 140), color).save(buffer, "PNG")
    return SimpleUploadedFile("header.png", buffer.getvalue(), content_type="image/png")


def test_header_picture_changed_from_the_date_sheet_page(exam_setup, login_as, make_user):  # noqa: F811
    exam = exam_setup["exam"]
    assert login_as(exam_setup["principal"]).post(
        f"/exams/{exam.id}/date-sheet/", {"action": "header", "image": _png()}
    ).status_code == 403  # fmt: skip
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    assert "Change logo" in admin.get(f"/exams/{exam.id}/date-sheet/").content.decode()
    admin.post(f"/exams/{exam.id}/date-sheet/", {"action": "header", "image": _png()})
    assert PrintHeader.objects.count() == 1
    from apps.core import paths

    assert paths.banner().startswith("data:image/png;base64,")
    admin.post(f"/exams/{exam.id}/date-sheet/", {"action": "header_reset"})
    assert not PrintHeader.objects.exists()


def test_date_sheet_one_page_and_card_with_many_subjects(exam_setup, login_as, make_user):  # noqa: F811
    import re
    import shutil
    import subprocess
    import tempfile

    from apps.exams.models import Paper

    if not shutil.which("pdfinfo"):
        pytest.skip("pdfinfo is not installed")

    def pages(content):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(content)
            f.flush()
            out = subprocess.run(["pdfinfo", f.name], capture_output=True, text=True, check=True).stdout
        return int(re.search(r"Pages:\s+(\d+)", out).group(1))

    exam, level = exam_setup["exam"], exam_setup["section"].class_level
    exam.starts_on, exam.ends_on = dt.date(2026, 11, 2), dt.date(2026, 11, 20)  # 19 days
    exam.save()
    for i in range(10):
        s, _ = Subject.objects.get_or_create(code=f"extra-{i}", defaults={"name": f"Extra Subject {i}"})
        Paper.objects.create(exam=exam, class_level=level, subject=s, total_marks=30, date=dt.date(2026, 11, 2 + i))
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    pdf = admin.get(f"/exams/{exam.id}/date-sheet.pdf")
    assert pages(pdf.content) == 1
    client = login_as(exam_setup["principal"])
    card = client.get(f"/exams/{exam.id}/section/{exam_setup['section'].id}/result-cards.pdf")
    assert pages(card.content) == 2  # two students, one page each, even with 12 subjects
