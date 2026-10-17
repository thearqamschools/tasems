"""The staff screen frame (Phase 4, M1): grouped sidebar, branch picker, and actions shown only when allowed."""

import datetime as dt

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.academics.models import Section
from apps.accounts.models import Scope, User
from apps.exams.models import Exam
from apps.fees.models import Voucher

pytestmark = pytest.mark.django_db

DEMO_STAFF = ["demo-principal", "demo-teacher", "demo-accountant", "demo-admissions", "demo-headoffice"]


@pytest.fixture
def demo(monkeypatch, settings):
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    settings.DEMO_MODE = True
    call_command("seed_demo", verbosity=0)


def _on(monkeypatch, day):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: day)


def _last(weekday):
    today = timezone.localdate()
    return today - dt.timedelta(days=(today.weekday() - weekday) % 7)


@pytest.mark.parametrize("username", DEMO_STAFF)
def test_every_menu_item_opens(demo, login_as, username):
    """The sidebar only lists pages the person may open: no menu item ends in a refusal."""
    client = login_as(User.objects.get(username=username))
    response = client.get("/")
    assert response.status_code == 200
    groups = response.context["nav_groups"]
    urls = [item["url"] for group in groups for item in group["items"]]
    assert urls and urls[0] == "/"
    for url in urls:
        assert client.get(url).status_code == 200, url


def test_menu_is_grouped_and_marks_the_current_page(demo, login_as):
    client = login_as(User.objects.get(username="demo-principal"))
    groups = client.get("/fees/defaulters/").context["nav_groups"]
    labels = [g["label"] for g in groups]
    assert labels[:5] == ["Overview", "Students", "Academics", "Finance", "Staff"]
    active = [i for g in groups for i in g["items"] if i["active"]]
    assert [i["url"] for i in active] == ["/fees/defaulters/"]  # the closest match, not "/fees/" as well


def test_teacher_menu_has_no_finance_or_staff_admin(demo, login_as):
    client = login_as(User.objects.get(username="demo-teacher"))
    urls = {i["url"] for g in client.get("/").context["nav_groups"] for i in g["items"]}
    assert "/fees/" not in urls and "/staff/" not in urls and "/staff/me/" in urls


def test_branch_picker_lists_branches_by_head_office(org, make_user, login_as):
    client = login_as(make_user("network_admin", Scope.NETWORK))
    body = client.get("/").content.decode()
    assert 'class="branch-picker"' in body and "data-branch-filter" in body
    for branch in (org["samanabad"], org["fsd_franchise"], org["lhr_franchise"]):
        assert f'name="branch" value="{branch.pk}"' in body
    panel = body[body.index("branch-panel") : body.index("</details>")]
    assert panel.index(org["fsd"].name) < panel.index(org["fsd_franchise"].name) < panel.index(org["lhr"].name)
    client.post("/branch/switch/", {"branch": org["lhr_franchise"].pk})
    assert client.session.get("current_branch_id") == org["lhr_franchise"].pk


def test_one_branch_shows_its_name_without_a_picker(org, make_user, login_as):
    body = login_as(make_user("principal", Scope.BRANCH, org["samanabad"])).get("/").content.decode()
    assert 'class="branch-picker"' not in body and org["samanabad"].name in body


def test_take_register_offered_only_on_a_school_day(demo, login_as, monkeypatch):
    client = login_as(User.objects.get(username="demo-teacher"))
    _on(monkeypatch, _last(4))  # Friday: Class 4 attends
    assert "/attendance/section/" in client.get("/").content.decode()
    _on(monkeypatch, _last(5))  # Saturday: Class 4 does not attend (D-023)
    assert "/attendance/section/" not in client.get("/").content.decode()


def test_remarks_and_ratings_buttons_follow_permissions(demo, login_as):
    exam = Exam.objects.first()
    own = Section.objects.get(class_teacher__username="demo-teacher")
    other = Section.objects.create(branch=own.branch, session=own.session, class_level=own.class_level, name="Z")
    teacher = login_as(User.objects.get(username="demo-teacher"))
    assert "/remarks/" in teacher.get(f"/exams/{exam.pk}/section/{own.pk}/").content.decode()
    assert "/ratings/" in teacher.get(f"/exams/section/{own.pk}/results/").content.decode()
    assert "/remarks/" not in teacher.get(f"/exams/{exam.pk}/section/{other.pk}/").content.decode()
    assert "/ratings/" not in teacher.get(f"/exams/section/{other.pk}/results/").content.decode()
    assert teacher.get(f"/exams/{exam.pk}/section/{other.pk}/remarks/").status_code == 403
    assert teacher.get(f"/exams/section/{other.pk}/ratings/").status_code == 403


def test_receive_link_only_for_people_who_take_payments(demo, login_as, client):
    month = Voucher.objects.order_by("-issued_on").first().issued_on.strftime("%Y-%m")
    url = f"/fees/vouchers/?month={month}"
    accountant = login_as(User.objects.get(username="demo-accountant")).get(url).content.decode()
    assert "/receive/" in accountant
    client.logout()
    admissions = login_as(User.objects.get(username="demo-admissions")).get(url).content.decode()
    assert "/receive/" not in admissions
