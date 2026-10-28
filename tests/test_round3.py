"""Round 3 (project lead, 28 Oct 2026): sections table and campuses, parent mobiles, Parent Tree slip, branch
contact numbers, no father email."""

import datetime as dt
import socket
import threading

import pytest

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.organisation.models import Campus
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(org):
    branch = org["samanabad"]
    girls = Campus.objects.create(branch=branch, name="Girls Campus", gender_group="girls")
    boys = Campus.objects.create(branch=branch, name="Boys Campus", gender_group="boys")
    five = Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="class-5"), name="Rose",
        campus=girls,
    )  # fmt: skip
    one = Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="class-1"), name="Rose",
        campus=girls,
    )  # fmt: skip

    def kid(adm, name, section, status="active", gender="female"):
        s = Student.objects.create(
            branch=branch, admission_no=adm, first_name=name, gender=gender, father_name="Asad Ali",
            father_cnic="3310012345671", admission_date=dt.date(2026, 4, 1), status=status,
        )  # fmt: skip
        Enrolment.objects.create(branch=branch, student=s, session=org["session"], section=section)
        return s

    ifrah = kid("3937", "Ifrah", five)
    haniya = kid("3935", "Haniya", one)
    left = kid("3930", "Left", one, status="withdrawn")
    father = Guardian.objects.create(branch=branch, full_name="Asad Ali", phone="03001234567")
    mother = Guardian.objects.create(branch=branch, full_name="Mother", phone="03217654321")
    StudentGuardian.objects.create(student=ifrah, guardian=father, relationship="father", is_primary_contact=True)
    StudentGuardian.objects.create(student=ifrah, guardian=mother, relationship="mother")
    return {"branch": branch, "girls": girls, "boys": boys, "ifrah": ifrah, "haniya": haniya, "left": left}


def test_parent_tree_lists_current_brothers_and_sisters(school, make_user, login_as):
    client = login_as(make_user("admissions_officer", Scope.BRANCH, school["branch"]))
    page = client.get(f"/students/{school['haniya'].id}/parent-tree/").content.decode()
    assert "Parent Tree" in page and "Asad Ali" in page and "041-2660265" in page and "0339-2406479" in page
    assert "Ifrah" in page and "3937" in page and "Haniya" in page and "Left" not in page  # left school: not on it
    assert page.index("Ifrah") < page.index("Haniya")  # higher class first, as on the old slip
    assert "<td>Girls</td>" in page and "<td>Five</td>" in page
    assert client.get(f"/students/{school['left'].id}/parent-tree/").status_code == 404  # only current students
    detail = client.get(f"/students/{school['ifrah'].id}/").content.decode()
    assert detail.count(f'action="/students/{school["ifrah"].id}/parent-tree/"') == 2  # icon by the name and the button
    assert "/parent-tree/" not in client.get(f"/students/{school['left'].id}/").content.decode()


def fake_printer():
    """A network receipt printer on this computer: keeps what it receives."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    got = bytearray()

    def serve():
        conn, _ = server.accept()
        with conn:
            while chunk := conn.recv(65536):
                got.extend(chunk)
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return f"127.0.0.1:{server.getsockname()[1]}", got, thread


def test_parent_tree_prints_straight_to_the_network_printer(school, make_user, login_as):
    """Project lead, 28 Oct 2026: no print window — the slip comes out of the LAN receipt printer at once."""
    client = login_as(make_user("admissions_officer", Scope.BRANCH, school["branch"]))
    url = f"/students/{school['haniya'].id}/parent-tree/"
    json = {"HTTP_ACCEPT": "application/json"}
    answer = client.post(url, **json)
    assert answer.status_code == 503 and "No receipt printer is set" in answer.json()["message"]
    address, got, thread = fake_printer()
    school["branch"].receipt_printer = address
    school["branch"].save()
    answer = client.post(url, **json)
    thread.join(5)
    assert answer.json() == {"ok": True, "message": "Parent Tree printed: 2 students."}
    assert b"THE ARQAM SCHOOLS" in got and b"Ifrah" in got and b"Haniya" in got and b"Left" not in got
    assert b"041-2660265" in got and got.endswith(b"\x1dVB\x00")  # paper cut at the end
    back = client.post(url, {"next": "/students/"})  # without JavaScript: back to the list with a note
    assert back.status_code == 302 and back.url == "/students/"


def test_students_list_shows_both_parent_mobiles_and_parent_tree(school, make_user, login_as):
    client = login_as(make_user("admissions_officer", Scope.BRANCH, school["branch"]))
    page = client.get("/students/").content.decode()
    assert "03001234567" in page and "03217654321" in page
    assert f"/students/{school['ifrah'].id}/parent-tree/" in page and "Parent Tree" in page


def test_father_email_is_not_asked(school, make_user, login_as):
    client = login_as(make_user("admissions_officer", Scope.BRANCH, school["branch"]))
    page = client.get(f"/students/{school['ifrah'].id}/edit/").content.decode()
    assert 'name="father_email"' not in page and 'name="email"' in page


def test_sections_page_and_campus_rules(school, make_user, login_as):
    client = login_as(make_user("branch_owner", Scope.BRANCH, school["branch"]))
    page = client.get("/setup/sections/").content.decode()
    assert "<th>Class</th><th>Section</th><th>Boys / Girls</th><th>Campus</th>" in page
    assert "Boys and Girls" in page and "Boys and girls" not in page
    form = client.get("/setup/sections/new/").content.decode()
    assert form.index(">Girls Campus<") < form.index(">Boys Campus<") and "Samanabad" not in form.split("campus")[-1]
    data = {"class_level": ClassLevel.objects.get(code="class-2").id, "name": "Tulip", "gender_group": "mixed"}
    assert "This field is required" in client.post("/setup/sections/new/", data).content.decode()
    client.post("/setup/sections/new/", {**data, "campus": school["girls"].id})  # boys and girls in the girls campus
    assert Section.objects.filter(name="Tulip", campus=school["girls"]).exists()
    bad = {**data, "name": "Daisy", "gender_group": "girls", "campus": school["boys"].id}
    assert "This campus is for Boys only" in client.post("/setup/sections/new/", bad).content.decode()


def test_branch_contact_numbers(org, make_user, login_as):
    samanabad = org["samanabad"]
    assert samanabad.contact_numbers == ["041-2660265", "041-2406479", "0339-2406479"]
    office = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"]))
    page = office.get(f"/setup/branches/{samanabad.id}/").content.decode()
    assert all(f'name="{n}"' in page for n in ("phone", "phone_2", "mobile_1", "mobile_2"))
    assert "Phone 1" in page and "Mobile 2" in page
