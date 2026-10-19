"""Student register screens and Excel import."""

import datetime as dt
import io

import pytest
from openpyxl import Workbook, load_workbook

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.people.importer import COLUMNS
from apps.people.models import Guardian, Student

pytestmark = pytest.mark.django_db

HEADERS = [h for _k, h, _r in COLUMNS]


def student_post(section=None, **overrides):
    data = {
        "admission_no": "100",
        "first_name": "Ali",
        "last_name": "Raza",
        "gender": "male",
        "date_of_birth": "2018-05-01",
        "admission_date": "2026-04-01",
        "b_form_no": "",
        "father_cnic": "33100-1112223-1",
        "father_name": "Raza Khan",
        "father_phone": "0300-1112223",
    }
    if section is not None:
        data.update(class_level=section.class_level_id, section_name=section.name)
    data.update(overrides)
    return data


def test_teacher_can_view_but_not_add(org, students, make_user, login_as):
    client = login_as(make_user("class_teacher", Scope.BRANCH, org["samanabad"]))
    assert client.get("/students/").status_code == 200
    assert client.get("/students/new/").status_code == 403
    assert client.get("/students/import/").status_code == 403


def test_list_shows_only_current_branch(org, students, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    body = client.get("/students/").content.decode()
    assert "S-1" in body and "F-1" not in body and "L-1" not in body


def test_other_branch_student_is_not_found(org, students, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    assert client.get(f"/students/{students['lhr_franchise'].pk}/").status_code == 404


def test_principal_adds_student_and_siblings_share_contact(org, section, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    response = client.post(
        "/students/new/",
        student_post(section, roll_no=1, mother_name="Amna Raza", mother_phone="0301-5556667", notes="Came from X"),
    )
    assert response.status_code == 302
    ali = Student.objects.get(admission_no="100")
    assert ali.enrolments.get().section == section and ali.father_name == "Raza Khan" and ali.notes == "Came from X"
    assert ali.guardian_links.get(relationship="father").is_primary_contact
    assert ali.guardian_links.get(relationship="mother").guardian.full_name == "Amna Raza"
    assert "101" in client.get("/students/new/").content.decode()  # next number filled in
    client.post("/students/new/", student_post(admission_no="101", first_name="Sara", gender="female"))
    assert Guardian.objects.filter(branch=org["samanabad"], phone="03001112223").count() == 1
    assert Guardian.objects.get(phone="03001112223").students.count() == 2


def test_form_rejects_bad_phone_and_duplicate_admission(org, students, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    body = client.post("/students/new/", student_post(admission_no="S-1", father_phone="12345")).content.decode()
    assert "numbers only" in body
    assert "Pakistani mobile number" in body
    Student.objects.filter(pk=students["samanabad"].pk).update(admission_no="555")
    body = client.post("/students/new/", student_post(admission_no="555", father_cnic="")).content.decode()
    assert "already used in this branch" in body and "13 digits" in body  # father CNIC is required


def test_form_rejects_girl_in_boys_section(org, make_user, login_as):
    boys = Section.objects.create(
        branch=org["samanabad"],
        session=org["session"],
        class_level=ClassLevel.objects.get(code="class-6"),
        name="A",
        gender_group="boys",
    )
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    body = client.post("/students/new/", student_post(boys, gender="female")).content.decode()
    assert "for Boys only" in body
    assert not Student.objects.filter(admission_no="100").exists()


def test_edit_student_records_history(org, students, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    s = students["samanabad"]
    client.post(f"/students/{s.pk}/edit/", student_post(admission_no="S-1", first_name="Bilal", status="active"))
    s.refresh_from_db()
    assert s.first_name == "Bilal"
    assert "first_name" in client.get(f"/students/{s.pk}/").content.decode()


def xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append([h + " *" for h in HEADERS])
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    buffer.name = "students.xlsx"
    return buffer


def row(adm, name, gender, klass, section, phone="03001234567", date=dt.date(2026, 4, 1)):
    return [adm, name, "", gender, "", date, "", klass, section, "", "Parent", phone, "Father"]


def test_template_downloads(org, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    response = client.get("/students/import/template.xlsx")
    wb = load_workbook(io.BytesIO(response.content))
    assert wb.active.cell(1, 1).value == "Admission No *"


def test_import_reports_every_problem_and_saves_nothing(org, students, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    file = xlsx(
        [
            row("S-1", "Dup", "Male", "Class 1", "A"),  # admission no. already exists
            row("N-1", "X", "Unknown", "Class 1", "A"),  # bad gender
            row("N-2", "Y", "Male", "Class 99", "A"),  # unknown class
            row("N-3", "Z", "Female", "Class 2", "A", phone="123"),  # bad phone
            row("N-3", "Z2", "Female", "Class 2", "A"),  # repeated in file
            row("N-4", "Girl", "Female", "Class 6", "A"),
            row("N-5", "Boy", "Male", "Class 6", "A"),  # boys and girls in one Class 6 section
        ]
    )
    body = client.post("/students/import/", {"step": "check", "file": file}).content.decode()
    for text in [
        "Already exists in this branch",
        "Use Male or Female",
        "Unknown class",
        "Not a Pakistani mobile number",
        "Repeated in this file",
        "cannot share section",
    ]:
        assert text in body, text
    assert Student.objects.filter(branch=org["samanabad"]).count() == 1


def test_import_saves_all_rows_and_creates_sections(org, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    file = xlsx(
        [
            row("N-1", "Ahmed", "Boy", "PG", "A"),
            row("N-2", "Ayesha", "Girl", "1", "A", phone="+92 301 2345678"),
            row("N-3", "Hamza", "M", "Pre-9", "Rose", date="15/04/2026"),
            row("N-4", "Fatima", "F", "Class 6", "B"),
        ]
    )
    body = client.post("/students/import/", {"step": "check", "file": file}).content.decode()
    assert "4 students are ready to import" in body
    token = client.session["import_token"]["token"]
    response = client.post("/students/import/", {"step": "import", "token": token})
    assert response.status_code == 302
    imported = Student.objects.filter(branch=org["samanabad"])
    assert imported.count() == 4
    assert imported.get(admission_no="N-3").admission_date == dt.date(2026, 4, 15)
    assert Section.objects.get(class_level__code="pre-9", name="Rose").gender_group == "boys"
    assert Section.objects.get(class_level__code="class-6", name="B").gender_group == "girls"
    assert Section.objects.get(class_level__code="play-group", name="A").gender_group == "mixed"
    assert Guardian.objects.filter(phone="03012345678").exists()
    # The same token cannot be used twice.
    again = client.post("/students/import/", {"step": "import", "token": token})
    assert again.status_code == 302 and Student.objects.filter(branch=org["samanabad"]).count() == 4


def test_head_office_home_lists_its_branches(org, students, make_user, login_as):
    client = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"]))
    body = client.get("/").content.decode()
    assert "Test FSD Franchise" in body and "Test LHR Franchise" not in body


def test_branch_switcher_refuses_other_branches(org, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    client.post("/branch/switch/", {"branch": org["lhr_franchise"].pk})
    assert client.session.get("current_branch_id") is None


def test_health_check_needs_no_login(client):
    response = client.get("/healthz")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_head_office_sees_todays_registers_per_branch(org, students, make_user, login_as):
    body = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])).get("/").content.decode()
    assert "Registers taken today" in body and "Diaries published today" in body


def test_subject_group_only_for_pre9_to_10(org, make_user, login_as):
    def section(code):
        level = ClassLevel.objects.get(code=code)
        return Section.objects.create(branch=org["samanabad"], session=org["session"], class_level=level, name="Rose")

    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    nine, five = section("class-9"), section("class-5")
    body = client.post("/students/new/", student_post(nine)).content.decode()
    assert "Choose Biology or Computer" in body
    client.post("/students/new/", student_post(nine, subject_group="computer"))
    assert Student.objects.get(admission_no="100").subject_group == "computer"
    client.post("/students/new/", student_post(five, admission_no="101", subject_group="biology"))
    assert Student.objects.get(admission_no="101").subject_group == ""  # not used below Pre-9th


def test_discount_chosen_at_admission(org, section, make_user, login_as):
    from apps.fees.models import Concession, DiscountType

    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    staff_half = DiscountType.objects.get(name="Staff child (50%)")
    scholarship = DiscountType.objects.get(name="Scholarship (100%)")
    client.post("/students/new/", student_post(section, discount_type=staff_half.id))
    c = Concession.objects.get(student__admission_no="100")
    assert c.value == 50 and c.status == "approved" and c.head.code == "tuition" and c.discount_type == staff_half
    client.post("/students/new/", student_post(section, admission_no="101", discount_type=scholarship.id))
    assert Concession.objects.get(student__admission_no="101").status == "pending"  # 100% waits for approval
    edit = client.get(f"/students/{Student.objects.get(admission_no='100').pk}/edit/").content.decode()
    assert "discount_type" not in edit  # later discounts go through the fee account


def test_father_cnic_typed_with_dashes(org, section, make_user, login_as):
    from apps.people.models import Student

    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    client.post(
        "/students/new/",
        student_post(section, admission_no="701", father_name="Abdul Rauf", father_cnic="33100-1234567-1"),
    )
    assert Student.objects.get(admission_no="701").father_cnic == "3310012345671"
    body = client.post("/students/new/", student_post(admission_no="702", father_cnic="1234")).content.decode()
    assert "13 digits" in body


OLD_REPORT = """
<html><head><style>@page {{ size: A4 landscape; margin: 10mm; }} table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid #000; padding: 3px; font-size: 9pt; }}</style></head><body>
<p>THE ARQAM SCHOOLS</p><p>Student Data</p>
<p>Count ( 3 ) Campus (Boys) Class : (Pre Nine) Section : (Rose)</p>
<table><tr><th>Comp. Code</th><th>Student Name</th><th>Father Name</th><th>Class</th><th>Section</th>
<th>Mon. Fee</th><th>Mobile</th><th>Other Number</th><th>CNIC/Occupation</th></tr>
{rows}</table></body></html>
"""


def old_report_pdf():
    from weasyprint import HTML

    rows = [
        ("9001", "Test Boy One", "Test Father One", "Pre<br>Nine", "Rose", "2900", "+923001112223<br>03211234567", "",
         "3310011111111"),
        ("9002", "Test Boy Two", "Test Father Two", "Pre<br>Nine", "Rose", "4300", "+923002223334", "2669650",
         "3310022222222<br>School"),
        ("9003", "Test Boy Three", "Test Father Three", "Pre<br>Nine", "Rose", "4000", "+923003334445", "", ""),
    ]  # fmt: skip
    html = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return HTML(string=OLD_REPORT.format(rows=html)).write_pdf()


def test_import_old_software_pdf_report(org, make_user, login_as):
    from apps.fees import services as fees
    from apps.fees.models import Concession, FeeHead, FeeRate

    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    upload = io.BytesIO(old_report_pdf())
    upload.name = "Student Data.pdf"
    page = client.post("/students/import/", {"step": "check", "file": upload})
    result = page.context["result"]
    assert result.ok, result.errors
    assert result.defaulted_admission_dates == 3
    client.post("/students/import/", {"step": "import", "token": page.context["token"]})
    one = Student.objects.get(admission_no="9001")
    assert (one.gender, one.father_name, one.father_cnic) == ("male", "Test Father One", "3310011111111")
    assert one.admission_date == org["session"].starts_on
    link = one.guardian_links.get()
    assert (link.guardian.phone, link.guardian.alt_phone) == ("03001112223", "03211234567")
    two = Student.objects.get(admission_no="9002")
    assert two.guardian_links.get().guardian.occupation == "School"
    assert one.enrolments.get().section.class_level.code == "pre-9"
    assert one.enrolments.get().section.gender_group == "boys"
    # the old monthly fee carries over exactly, whatever the sibling rule would say
    assert Concession.objects.get(student=one).value == 2900
    tuition = FeeHead.objects.get(code="tuition")
    head_rate = FeeRate.objects.get(branch=org["samanabad"], head=tuition)
    gross, discount, reason = fees.price(
        tuition, head_rate, org["session"].starts_on, True, [Concession.objects.get(student=one)]
    )
    assert (gross - discount, reason) == (2900, "Agreed fee")
