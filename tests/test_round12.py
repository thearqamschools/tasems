"""Round 12 (project lead, 18 Nov 2026): attendance machine read only when asked or at a chosen interval, one
connection at a time, a 30-minute wait after the machine does not answer; monthly sheet print and layout."""

import datetime as dt
import threading

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Scope
from apps.hr import services as S
from apps.hr import zk
from apps.hr.models import AttendanceMachine

pytestmark = pytest.mark.django_db


@pytest.fixture
def machine(org, make_user):
    director = make_user("branch_owner", Scope.BRANCH, org["samanabad"])
    m = AttendanceMachine.objects.create(branch=org["samanabad"], name="Gate", host="127.0.0.1", port=1,
                                         added_by=director)  # fmt: skip
    return {"machine": m, "director": director}


def test_read_by_itself_never_by_default_and_choices(machine, login_as, monkeypatch):
    m = machine["machine"]
    assert m.read_every == 0 and not m.is_due(timezone.now())  # starts at "Never"
    calls = []
    monkeypatch.setattr(S, "read_machine", lambda mach, user=None: calls.append(mach.pk) or "ok")
    import apps.hr.management.commands.read_machines as command

    monkeypatch.setattr(command, "read_machine", S.read_machine)
    call_command("read_machines")
    assert calls == []
    client = login_as(machine["director"])
    page = client.get("/staff/attendance/machines/").content.decode()
    assert "Every 15 minutes" in page and "Every hour" in page and "Every 5" not in page
    client.post("/staff/attendance/machines/", {"action": "save", "machine": m.id, "name": "Gate", "host": "127.0.0.1",
                                                "port": "1", "comm_key": "0", "read_every": "30"})  # fmt: skip
    m.refresh_from_db()
    assert m.read_every == 30 and m.is_due(timezone.now())
    call_command("read_machines")
    assert calls == [m.pk]
    m.last_read_at = timezone.now() - dt.timedelta(minutes=10)
    assert not m.is_due(timezone.now())  # not before 30 minutes


def test_no_answer_waits_30_minutes_but_get_now_still_tries(machine, monkeypatch):
    m = machine["machine"]
    m.read_every = 15
    m.save()

    def silent(*args, **kwargs):
        raise zk.MachineError("no answer")

    monkeypatch.setattr(zk, "read", silent)
    S.read_machine(m)
    m.refresh_from_db()
    assert not m.last_ok and m.paused_until > timezone.now() + dt.timedelta(minutes=29)
    later = timezone.now() + dt.timedelta(minutes=20)
    m.last_read_at = timezone.now() - dt.timedelta(hours=1)
    assert not m.is_due(later)  # waiting
    assert m.is_due(timezone.now() + dt.timedelta(minutes=31))


def test_one_connection_at_a_time(monkeypatch):
    lock = zk._lock_for("10.0.0.9", 4370)
    lock.acquire()
    try:
        with pytest.raises(zk.MachineError, match="busy"):
            zk.read("10.0.0.9", 4370, wait=0.1)
    finally:
        lock.release()
    started, release = threading.Event(), threading.Event()

    def slow(*args):
        started.set()
        release.wait(2)
        return "done"

    monkeypatch.setattr(zk, "_read_once", slow)
    results = []
    first = threading.Thread(target=lambda: results.append(zk.read("10.0.0.9", 4370)))
    first.start()
    started.wait(2)
    second = threading.Thread(target=lambda: results.append(zk.read("10.0.0.9", 4370, wait=3)))
    second.start()
    release.set()
    first.join(3)
    second.join(3)
    assert results == ["done", "done"]  # the second waited for the first instead of failing


def test_monthly_sheet_print_layout(org, make_user, login_as):
    client = login_as(make_user("branch_owner", Scope.BRANCH, org["samanabad"]))
    page = client.get("/staff/attendance/month/").content.decode()
    assert 'class="sheet-table month-sheet"' in page and "size: A4 landscape" in page
    assert '<p class="no-print"><a href="/staff/">' in page
