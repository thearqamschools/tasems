"""Hiring (R8, project lead 11 Nov 2026): CV bank, one record per person, relevant or not, vacancies with matching
CVs, interview mark sheet, staff record from the hired candidate, the Bin (2 years, then 30 days)."""

import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import Scope
from apps.hiring import services as S
from apps.hiring.models import Application, Candidate, CVFile, Post, Vacancy
from apps.hr.models import Employee, Qualification

pytestmark = pytest.mark.django_db


@pytest.fixture
def hiring(org, make_user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    branch = org["samanabad"]
    return {
        "branch": branch,
        "director": make_user("branch_owner", Scope.BRANCH, branch, first_name="Demo", last_name="Director"),
        "admin": make_user("admissions_officer", Scope.BRANCH, branch),
        "teacher": make_user("class_teacher", Scope.BRANCH, branch),
        "teacher_post": Post.objects.get(name="Teacher"),
    }


def photo(name="page1.jpg"):
    return SimpleUploadedFile(name, b"\xff\xd8\xff fake jpeg", content_type="image/jpeg")


def cv_data(post, **extra):
    data = {
        "received_on": "2026-11-10", "channel": "whatsapp", "post": post.id, "full_name": "Ayesha Noreen",
        "father_name": "Muhammad Aslam", "gender": "female", "mobile": "0300-1234567", "address": "Gulistan Colony",
        "qualification": "M.Sc Chemistry", "experience_years": "3", "subjects": ["chemistry", "science"],
        "levels": ["middle"], "relevance": "relevant",
        "education-TOTAL_FORMS": "1", "education-INITIAL_FORMS": "0", "education-0-degree": "M.Sc Chemistry",
        "education-0-institute": "GC University Faisalabad", "education-0-year": "2019",
        "experience-TOTAL_FORMS": "1", "experience-INITIAL_FORMS": "0", "experience-0-organisation": "",
    }  # fmt: skip
    data.update(extra)
    return data


def test_add_cv_with_photos_and_file_is_private(hiring, login_as):
    client = login_as(hiring["admin"])  # the Admin enters CVs
    answer = client.post("/hiring/add/", {**cv_data(hiring["teacher_post"]), "files": [photo(), photo("page2.jpg")]})
    c = Candidate.objects.get()
    assert answer.status_code == 302 and answer.url == f"/hiring/{c.id}/"
    assert c.last_received_on == dt.date(2026, 11, 10) and c.subjects == ["chemistry", "science"]
    assert c.education.get().institute == "GC University Faisalabad" and not c.experience.exists()
    files = CVFile.objects.filter(cv__candidate=c)
    assert files.count() == 2
    assert client.get(f"/hiring/file/{files[0].id}/").status_code == 200
    assert login_as(hiring["teacher"]).get(f"/hiring/file/{files[0].id}/").status_code == 403
    page = login_as(hiring["director"]).get(f"/hiring/{c.id}/").content.decode()
    assert "Ayesha Noreen" in page and "WhatsApp" in page and "Kept until" in page


def test_same_mobile_is_one_person(hiring, login_as):
    client = login_as(hiring["director"])
    client.post("/hiring/add/", cv_data(hiring["teacher_post"]))
    first = Candidate.objects.get()
    again = cv_data(hiring["teacher_post"], received_on="2026-11-11", mobile="+92 300 1234567", channel="email")
    page = client.post("/hiring/add/", {**again, "files": [photo()]}).content.decode()
    assert "already in the CV bank" in page and Candidate.objects.count() == 1
    pending = page.split('name="pending" value="')[1].split('"')[0]
    client.post("/hiring/add/", {**again, "pending": pending, "same_person": "attach"})
    first.refresh_from_db()
    assert Candidate.objects.count() == 1 and first.cvs.count() == 2 and first.last_received_on == dt.date(2026, 11, 11)
    assert CVFile.objects.filter(cv__candidate=first).count() == 1  # the photo chosen before the question is kept
    client.post("/hiring/add/", {**again, "full_name": "Ayesha Bibi", "same_person": "new"})
    assert Candidate.objects.count() == 2


def test_cv_bank_filters_and_vacancy_to_staff(hiring, login_as):
    client = login_as(hiring["director"])
    post = hiring["teacher_post"]
    client.post("/hiring/add/", cv_data(post, received_on="2026-09-01", full_name="Older", mobile="03001111111",
                                        subjects=["english"]))  # fmt: skip
    client.post("/hiring/add/", cv_data(post, received_on="2026-11-01", full_name="Newer", mobile="03002222222",
                                        subjects=["english"]))  # fmt: skip
    client.post("/hiring/add/", cv_data(post, full_name="Far", mobile="03003333333", subjects=["english"],
                                        relevance="not_relevant"))  # fmt: skip
    client.post("/hiring/add/", cv_data(post, full_name="Urdu one", mobile="03004444444", subjects=["urdu"]))
    page = client.get("/hiring/?subject=english&level=middle&relevance=relevant").content.decode()
    page = page[page.index("<tbody>") :]  # the table (the messages above it name every CV saved)
    assert page.index("Newer") < page.index("Older") and "Urdu one" not in page and "Far" not in page
    client.post("/hiring/vacancies/", {"post": post.id, "subject": "english", "level": "middle", "openings": "1"})
    v = Vacancy.objects.get()
    matching = [c.full_name for c in S.matching(v)]
    assert matching == ["Newer", "Older"]  # not relevant and other subjects left out; latest first
    newer = Candidate.objects.get(full_name="Newer")
    client.post(f"/hiring/vacancies/{v.id}/", {"action": "shortlist", "candidate": [newer.id]})
    app = Application.objects.get()
    newer.refresh_from_db()
    assert newer.status == "in_process"
    client.post(f"/hiring/vacancies/{v.id}/", {"action": "move", "application": app.id, "stage": "interview",
                                               "interview_at": "2026-11-13T10:00"})  # fmt: skip
    marks = {"held_on": "2026-11-13", "interviewers": "Principal, Coordinator", "subject_knowledge": "8",
             "teaching": "7", "communication": "9", "character": "9", "experience": "4", "impression": "4",
             "decision": "select"}  # fmt: skip
    client.post(f"/hiring/sheet/{app.id}/", marks)
    app.refresh_from_db()
    assert app.stage == "selected" and app.sheet.total == 41
    bad = client.post(f"/hiring/sheet/{app.id}/", {**marks, "experience": "9"}).content.decode()
    assert "less than or equal to 5" in bad
    form = client.get(f"/staff/new/?candidate={newer.id}").content.decode()
    assert 'value="Newer"' in form and "Filled in from the CV" in form
    staff = {"candidate": newer.id, "code": "T-21", "full_name": "Newer", "father_name": "Muhammad Aslam",
             "gender": "female", "designation": "Junior Teacher", "staff_type": "teaching", "joined_on": "2026-11-15",
             "status": "active"}  # fmt: skip
    assert client.post("/staff/new/", staff).status_code == 302
    e = Employee.objects.get(code="T-21")
    newer.refresh_from_db()
    v.refresh_from_db()
    app.refresh_from_db()
    assert newer.status == "hired" and newer.hired_employee == e and app.stage == "joined" and v.status == "filled"
    assert Qualification.objects.filter(employee=e, degree="M.Sc Chemistry").exists()
    assert "Newer" not in [c.full_name for c in S.matching(Vacancy.objects.create(
        branch=hiring["branch"], post=post, created_by=hiring["director"]))]  # fmt: skip


def test_bin_after_two_years_and_deleted_after_30_days(hiring, login_as):
    branch, user, post = hiring["branch"], hiring["director"], hiring["teacher_post"]
    today = timezone.localdate()
    old = Candidate.objects.create(branch=branch, full_name="Old CV", post=post, created_by=user,
                                   last_received_on=today - dt.timedelta(days=731))  # fmt: skip
    busy = Candidate.objects.create(branch=branch, full_name="In process", post=post, created_by=user,
                                    last_received_on=today - dt.timedelta(days=800), status="in_process")  # fmt: skip
    recent = Candidate.objects.create(branch=branch, full_name="Recent", post=post, created_by=user,
                                      last_received_on=today - dt.timedelta(days=700))  # fmt: skip
    assert S.cleanup() == (1, 0)
    old.refresh_from_db()
    busy.refresh_from_db()
    recent.refresh_from_db()
    assert old.binned_at and not busy.binned_at and not recent.binned_at
    page = login_as(user).get("/hiring/").content.decode()
    assert "Old CV" not in page and "Bin (1)" in page
    assert S.cleanup(now=old.binned_at + dt.timedelta(days=31))[1] == 1
    assert not Candidate.objects.filter(pk=old.pk).exists()


def test_roles_menu_and_posts(hiring, login_as):
    admin = login_as(hiring["admin"])
    menu = admin.get("/hiring/").content.decode()
    assert "CV bank" in menu and "Add a CV" in menu
    assert login_as(hiring["teacher"]).get("/hiring/").status_code == 403
    director = login_as(hiring["director"])
    director.post("/hiring/posts/", {"name": "Librarian"})
    assert Post.objects.filter(name="Librarian").exists()
    names = set(Post.objects.values_list("name", flat=True))
    assert {"Designer", "Content Creator", "Graphic Designer", "Typist", "Teacher", "Guard"} <= names
