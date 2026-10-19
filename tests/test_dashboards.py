"""Role dashboards (Phase 4, M2): the right panels for each person, figures that agree with the module pages,
the network view for several branches, and charts that follow the design rules."""

import datetime as dt
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import Scope, User
from apps.dashboards.charts import BAR_MAX, column_chart
from apps.fees import reports
from apps.fees.models import month_start
from apps.organisation.models import Branch

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(monkeypatch, settings):
    monkeypatch.setenv("DEMO_PASSWORD", "Demo-pass-2026!")
    settings.DEMO_MODE = True
    call_command("seed_demo", verbosity=0)


def _dash(login_as, username):
    response = login_as(User.objects.get(username=username)).get("/")
    assert response.status_code == 200
    return response


def test_principal_sees_branch_fees_and_admissions(demo, login_as):
    ctx = _dash(login_as, "demo-principal").context
    for key in ("attendance", "classes", "fees", "admissions", "staff", "students"):
        assert key in ctx, key
    assert "my_classes" not in ctx and "network" not in ctx
    assert ctx["has_money"]


def test_teacher_sees_own_classes_not_money(demo, login_as):
    ctx = _dash(login_as, "demo-teacher").context
    assert [c["section"].class_teacher.username for c in ctx["my_classes"]] == ["demo-teacher"]
    assert "fees" not in ctx and not ctx["has_money"]
    assert "data-money-toggle" not in _dash(login_as, "demo-teacher").content.decode()


@pytest.mark.parametrize("username", ["demo-principal", "demo-teacher", "demo-accountant", "demo-admissions"])
def test_quick_actions_all_open(demo, login_as, username):
    client = login_as(User.objects.get(username=username))
    actions = client.get("/").context["quick_actions"]
    assert actions
    for url, _label, _icon in actions:
        assert client.get(url).status_code == 200, url


def test_fee_figures_match_the_fees_page(demo, login_as):
    ctx = _dash(login_as, "demo-principal").context
    branch = ctx["branch"]
    summary = reports.month_summary(branch, month_start(timezone.localdate()))
    fees = ctx["fees"]
    assert (fees["billed"], fees["collected"], fees["outstanding"], fees["defaulters"]) == (
        summary["billed"],
        summary["collected"],
        summary["outstanding"],
        summary["defaulters"],
    )
    # The daily chart adds up to the month's receipts so far.
    assert sum(Decimal(b["value"]) for b in fees["chart"]["bars"]) == summary["collected"]


def test_attendance_figures_add_up(demo, login_as):
    ctx = _dash(login_as, "demo-principal").context
    att = ctx["attendance"]
    taken = [c["register"] for c in ctx["classes"] if c["register"]]
    assert att["registers"] == len(taken)
    assert att["absent"] == sum(r.absent for r in taken)
    trend = ctx["attendance_trend"]
    assert trend and all(0 <= b["value"] <= 100 for b in trend["bars"])


def test_teacher_panel_follows_the_school_week(demo, login_as, monkeypatch):
    client = login_as(User.objects.get(username="demo-teacher"))
    today = timezone.localdate()
    saturday = today - dt.timedelta(days=(today.weekday() - 5) % 7)
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: saturday)
    card = client.get("/").context["my_classes"][0]
    assert not card["can_take"] and not card["can_write_diary"]  # Class 4 does not attend on Saturday (D-023)


def test_network_view_filters_sorts_and_shows_royalty(org, make_user, login_as):
    client = login_as(make_user("network_admin", Scope.NETWORK))
    ctx = client.get("/").context
    names = {r["branch"].name for r in ctx["network"]}
    assert {org["samanabad"].name, org["fsd_franchise"].name, org["lhr_franchise"].name} <= names
    lahore = client.get(f"/?ho={org['lhr'].pk}").context
    assert {r["branch"].head_office_id for r in lahore["network"]} == {org["lhr"].pk}
    by_name = client.get("/?sort=name").context["network"]
    assert [r["branch"].name.lower() for r in by_name] == sorted(r["branch"].name.lower() for r in by_name)
    # Network administrators hold fees.view_royalty: the figure is the Royalty page's own calculation.
    expected = sum((r.royalty for r in reports.royalty(list(Branch.objects.all()), timezone.localdate())), 0)
    assert ctx["network_totals"]["royalty"] == expected


def test_network_queries_do_not_grow_with_branches(org, make_user, login_as):
    client = login_as(make_user("network_admin", Scope.NETWORK))
    client.get("/")  # warm caches (permissions, session)
    with CaptureQueriesContext(connection) as few:
        client.get("/?sort=name")
    for i in range(12):
        Branch.objects.create(code=f"extra-{i}", name=f"Extra {i}", head_office=org["fsd"], city="Faisalabad")
    client.get("/")
    with CaptureQueriesContext(connection) as many:
        client.get("/?sort=name")
    assert len(many.captured_queries) <= len(few.captured_queries) + 2


def test_column_chart_follows_the_mark_rules():
    points = [{"label": str(d), "title": str(d), "value": v, "text": str(v)} for d, v in enumerate([10, 0, 55, 100])]
    chart = column_chart(points, percent=True)
    assert all(b["w"] <= BAR_MAX for b in chart["bars"])
    assert [t["text"] for t in chart["ticks"]] == ["0%", "25%", "50%", "75%", "100%"]
    assert chart["bars"][1]["path"] == ""  # a zero value draws no mark
    assert chart["bars"][-1]["is_last"] and chart["bars"][-1]["show_label"]
    assert column_chart([{"label": "1", "title": "1", "value": 0, "text": "0"}], money=True)["empty"]
