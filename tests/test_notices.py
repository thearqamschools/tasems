"""M8: notices for parents and staff, messages to parents without a paid service, installable parent portal."""

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel
from apps.accounts.models import Scope
from apps.fees import services as fees
from apps.notices import messaging as M
from apps.notices.models import MessageBatch, MessageTemplate, Notice, NoticeRead
from tests.test_parents import family, set_up  # noqa: F401 - shared parent fixture and sign-up helper

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def post_notice(client, **extra):
    data = {
        "where": "branch",
        "audience": "parents",
        "title": "Sports day",
        "body": "Sports day on Friday.",
        "publish_on": TODAY.isoformat(),
        **extra,
    }
    return client.post("/notices/new/", data)


def test_principal_posts_and_parents_of_that_class_see_it(client, login_as, family):  # noqa: F811
    staff = login_as(family["principal"])
    four = ClassLevel.objects.get(code="class-4")
    post_notice(staff, class_levels=[four.id])
    six = ClassLevel.objects.get(code="class-6")
    post_notice(staff, title="Class 6 trip", class_levels=[six.id])
    notice = Notice.objects.get(title="Sports day")
    assert notice.branch == family["branch"]
    staff.logout()
    set_up(client, login_as, family)
    home = client.get("/parents/").content.decode()
    assert "Sports day" in home and "Class 6 trip" not in home and "New" in home
    client.get(f"/parents/notices/{notice.id}/")
    assert NoticeRead.objects.filter(notice=notice).count() == 1
    other = Notice.objects.get(title="Class 6 trip")
    assert client.get(f"/parents/notices/{other.id}/").status_code == 404


def test_staff_notice_on_dashboard_and_parents_only_hidden_from_teachers(login_as, make_user, family):  # noqa: F811
    staff = login_as(family["principal"])
    post_notice(staff, audience="staff", title="Staff meeting")
    post_notice(staff, title="Parents only")
    staff.get("/notices/")  # the "posted" messages are shown here, not on the teacher's page (same test client)
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, family["branch"]))
    home = teacher.get("/").content.decode()
    assert "Staff meeting" in home and "Parents only" not in home
    hidden = Notice.objects.get(title="Parents only")
    assert teacher.get(f"/notices/{hidden.id}/").status_code == 404
    assert teacher.get("/notices/new/").status_code == 403


def test_network_notice_only_withdrawn_by_network(login_as, make_user, family):  # noqa: F811
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    page = admin.get("/notices/new/").content.decode()
    assert "Every branch of the network" in page
    post_notice(admin, where="network", title="Quaid Day")
    notice = Notice.objects.get(title="Quaid Day")
    assert notice.branch is None and notice.head_office is None
    principal = login_as(family["principal"])
    assert principal.post(f"/notices/{notice.id}/withdraw/").status_code == 403
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    admin.post(f"/notices/{notice.id}/withdraw/")
    notice.refresh_from_db()
    assert notice.is_withdrawn


def test_fee_reminders_are_filled_in_and_never_sent_by_themselves(login_as, family, org):  # noqa: F811
    principal = family["principal"]
    fees.generate_vouchers(
        family["branch"], org["session"], TODAY.replace(day=1), TODAY.replace(day=1), TODAY, principal
    )
    template = MessageTemplate.objects.get(name="Fee reminder (English)")
    client = login_as(principal)
    page = client.get(f"/notices/messages/?template={template.id}&audience=defaulters")
    rows = page.context["rows"]
    assert {r["student"].first_name for r in rows} == {"Ahmad", "Hira"}  # the stranger's family owes nothing billed
    first = rows[0]
    assert f"Rs \u2066{first['amount_due']:,.0f}\u2069" in first["message"]  # kept left-to-right in Urdu too
    assert family["branch"].name in first["message"]
    assert first["whatsapp"].startswith("https://wa.me/923001234567?text=")
    assert not MessageBatch.objects.exists()
    xlsx = client.get(f"/notices/messages/?template={template.id}&audience=defaulters&format=xlsx")
    assert xlsx.status_code == 200 and MessageBatch.objects.get().count == 2


def test_placeholders_and_phone_numbers():
    assert M.international("0300-1234567") == "923001234567"


def test_teacher_cannot_prepare_messages_or_edit_templates(login_as, make_user, family):  # noqa: F811
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, family["branch"]))
    assert teacher.get("/notices/messages/").status_code == 403
    principal = login_as(family["principal"])
    assert principal.get("/notices/messages/templates/").status_code == 403  # the same for every branch
    admin = login_as(make_user("network_admin", Scope.NETWORK))
    admin.post(
        "/notices/messages/templates/new/",
        {"name": "Exam reminder", "body": "{student} exams start soon.", "is_active": "on"},
    )
    assert MessageTemplate.objects.filter(name="Exam reminder").exists()


def test_parent_portal_is_installable(client):
    manifest = client.get("/parents/manifest.webmanifest").json()
    assert manifest["start_url"] == "/parents/" and len(manifest["icons"]) == 2
    sw = client.get("/parents/sw.js")
    assert sw["Content-Type"].startswith("application/javascript") and b"/parents/offline/" in sw.content
    assert "No internet connection" in client.get("/parents/offline/").content.decode()
    assert 'rel="manifest"' in client.get("/parents/login/").content.decode()
