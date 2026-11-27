"""Round 19 (project lead, 27 Nov 2026): subjects in the class's order and with short names everywhere, Comp. Code
order by default, and the sheet to fill by hand with the class teacher, total, obtained and %."""

import pytest

from apps.academics.models import CurriculumSubject, Subject
from apps.accounts.models import Scope

from .test_exam_documents import exam_setup  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def test_class_subjects_order_and_short_names_used_everywhere(exam_setup, login_as, make_user):  # noqa: F811
    level = exam_setup["section"].class_level
    english, urdu = Subject.objects.get(code="english"), Subject.objects.get(code="urdu")
    admin_user = make_user("network_admin", Scope.NETWORK)
    admin = login_as(admin_user)
    # Urdu first, then English (as dragged), with short names.
    admin.post(f"/setup/classes-subjects/?class={level.id}", {"subject": [english.id, urdu.id]})
    admin.post(f"/setup/classes-subjects/?class={level.id}", {
        "order": [urdu.id, english.id], "keep": [urdu.id, english.id],
        f"short_{urdu.id}": "URD", f"short_{english.id}": "ENG"})  # fmt: skip
    links = list(CurriculumSubject.objects.filter(class_level=level).order_by("sort_order"))
    assert [c.subject.code for c in links] == ["urdu", "english"]
    page = admin.get(f"/setup/classes-subjects/?class={level.id}").content.decode()
    assert "data-sortable" in page and page.index("Urdu") < page.index("English")
    client = login_as(exam_setup["principal"])
    marks = client.get(f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/marks/").content.decode()
    assert marks.index(">URD<") < marks.index(">ENG<")  # the class's order and the short names
    sheet = client.get(
        f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/marks/?print=1"
    ).content.decode()  # fmt: skip
    assert (
        "URD (50)" in sheet and "Obtained (100)" in sheet and "Total marks: 100" in sheet and "Class teacher:" in sheet
    )
    # Untick English: it leaves the class.
    admin = login_as(admin_user)  # the same test client: sign the admin in again
    admin.post(f"/setup/classes-subjects/?class={level.id}", {"order": [urdu.id, english.id], "keep": [urdu.id]})
    assert list(CurriculumSubject.objects.filter(class_level=level).values_list("subject__code", flat=True)) == ["urdu"]


def test_comp_code_order_by_default(exam_setup, login_as):  # noqa: F811
    a, b = exam_setup["kids"]
    a.admission_no, b.admission_no = "100", "20"
    a.save()
    b.save()
    client = login_as(exam_setup["principal"])
    url = f"/exams/{exam_setup['exam'].id}/section/{exam_setup['section'].id}/marks/"
    page = client.get(url).content.decode()
    assert page.index(">20<") < page.index(">100<")  # numbers in number order, smallest first
    sheet = client.get(f"{url}?print=1").content.decode()
    assert sheet.index(">20<") < sheet.index(">100<")
