"""Round 6 (project lead, 31 Oct 2026): payroll columns, attendance bonus, GP Fund / EOBI / other amounts,
advances and instalments, salary security, final settlement; Sell tickets; the ZKTeco attendance machine."""

import datetime as dt
import socket
import threading
from decimal import Decimal
from struct import pack, unpack

import pytest

from apps.accounts.models import Scope
from apps.hr import zk
from apps.hr.models import AttendanceMachine, Employee, Punch
from apps.payroll import services as P
from apps.payroll.models import Advance, AdvanceMonth, EmployeePay, ManualDays, PayrollRules, PayrollRun

pytestmark = pytest.mark.django_db
D = Decimal
OCT, NOV = dt.date(2026, 10, 1), dt.date(2026, 11, 1)


@pytest.fixture
def staff(org, make_user, monkeypatch):
    from django.utils import timezone

    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: dt.date(2026, 11, 5))
    branch = org["samanabad"]

    def person(code, designation, salary, **extra):
        e = Employee.objects.create(
            branch=branch, code=code, full_name=f"Staff {code}", gender="female", designation=designation,
            staff_type="support", joined_on=dt.date(2025, 1, 1), **extra,
        )  # fmt: skip
        EmployeePay.objects.create(branch=branch, employee=e, monthly_salary=salary)
        return e

    return {
        "branch": branch,
        "guard": person("G1", "Guard", D(31000)),
        "teacher": person("T1", "Senior Teacher", D(31000)),
        "accountant": make_user("accountant", Scope.BRANCH, branch, first_name="Demo", last_name="Accountant"),
        "director": make_user("branch_owner", Scope.BRANCH, branch),
        "person": person,
    }


def row_of(branch, month, employee):
    rows, _t = P.compute(branch, month)
    return next(r for r in rows if r["employee"] == employee)


def manual(branch, employee, month, absent=0, half=0, user=None):
    ManualDays.objects.update_or_create(
        branch=branch, employee=employee, month=month,
        defaults={"days_in_month": 31, "working_days": 26, "days_employed": 31, "absent_days": absent,
                  "leave_days": 0, "half_days": half, "entered_by": user},
    )  # fmt: skip


def test_bonus_only_for_listed_designations_and_full_attendance(staff):
    b = staff["branch"]
    assert row_of(b, OCT, staff["guard"])["bonus"] == D(1000)  # one day of 31,000 / 31
    assert row_of(b, OCT, staff["teacher"])["bonus"] == 0  # teachers are not in the list
    manual(b, staff["guard"], OCT, half=1, user=staff["accountant"])
    assert row_of(b, OCT, staff["guard"])["bonus"] == 0  # a half day stops the bonus
    rules = PayrollRules.for_branch(b)
    rules.bonus_designations = ["Guard", "Senior Teacher"]
    rules.save()
    assert row_of(b, OCT, staff["teacher"])["bonus"] == D(1000)


def test_payroll_page_columns_and_amounts_by_hand(staff, login_as):
    client = login_as(staff["accountant"])
    page = client.get("/payroll/?month=2026-10").content.decode()
    page = page[page.index("payroll-table") : page.index("</thead>")]
    heads = ["Code", "Name", "Designation", "Monthly salary", "Absent", "Half days", "Bonus", "GP Fund", "EOBI",
             "Advance", "Security", "Net pay"]  # fmt: skip
    positions = [page.index(f">{h}") for h in heads]
    assert positions == sorted(positions) and ">Unpaid leave<" not in page
    t = staff["teacher"]
    client.post(
        f"/payroll/staff/{t.id}/?month=2026-10",
        {"action": "extras", "gp_fund": "500", "eobi": "250", "other_deduction": "100",
         "other_deduction_reason": "Fine", "other_addition": "1000", "other_addition_reason": "Arrears"},
    )  # fmt: skip
    r = row_of(staff["branch"], OCT, t)
    assert (r["gp_fund"], r["eobi"], r["net"]) == (D(500), D(250), D(31000 - 500 - 250 - 100 + 1000))


def test_advances_one_month_and_instalments(staff, login_as):
    client = login_as(staff["accountant"])
    g, t = staff["guard"], staff["teacher"]
    client.post("/payroll/advances/", {"employee": t.id, "kind": "month", "amount": "5000", "given_on": "2026-10-03",
                                       "start_month": "2026-10", "method": "cash"})  # fmt: skip
    client.post("/payroll/advances/", {"employee": g.id, "kind": "instalments", "amount": "50000",
                                       "monthly_cut": "5000", "given_on": "2026-09-20", "start_month": "2026-10",
                                       "method": "cash", "approved_by": "Director"})  # fmt: skip
    assert row_of(staff["branch"], OCT, t)["net"] == D(26000)  # 31,000 − 5,000
    assert row_of(staff["branch"], OCT, g)["advance"] == D(5000)
    loan = Advance.objects.get(employee=g)
    client.post(f"/payroll/staff/{g.id}/?month=2026-10", {"action": "instalment", "advance": loan.id, "amount": "0"})
    assert AdvanceMonth.objects.get().amount == 0 and row_of(staff["branch"], OCT, g)["advance"] == 0  # skipped
    client.post(f"/payroll/staff/{g.id}/?month=2026-10", {"action": "instalment", "advance": loan.id, "amount": "2000"})
    client.post("/payroll/finalise/?month=2026-10")
    loan.refresh_from_db()
    assert loan.remaining() == D(48000) and Advance.objects.get(employee=t).remaining() == 0
    assert row_of(staff["branch"], NOV, g)["advance"] == D(5000)  # back to the usual cut
    page = client.get("/payroll/advances/").content.decode()
    assert "48,000" in page and "Staff G1" in page


def test_security_over_months_with_shortfall_and_settlement(staff, login_as, org):
    b = staff["branch"]
    new = staff["person"]("N1", "Junior Teacher", D(31000), keep_security=True, security_months=1,
                          security_from=OCT)  # fmt: skip
    manual(b, new, OCT, absent=10, user=staff["accountant"])
    r = row_of(b, OCT, new)
    assert r["security"] == D(21000) and r["net"] == 0  # all of a short first month
    client = login_as(staff["accountant"])
    client.post("/payroll/finalise/?month=2026-10")
    assert row_of(b, NOV, new)["security"] == D(10000)  # the rest from the next month
    # Leaving with an advance still due: taken from the security, the rest returned.
    Advance.objects.create(branch=b, employee=new, kind="instalments", amount=D(5000), monthly_cut=D(1000),
                           given_on=OCT, start_month=dt.date(2027, 1, 1), recorded_by=staff["accountant"])  # fmt: skip
    new.left_on, new.status = dt.date(2026, 11, 3), "left"
    new.save()
    page = client.get(f"/payroll/staff/{new.id}/settlement/").content.decode()
    assert "Final settlement" in page and "21,000" in page
    client.post(
        f"/payroll/staff/{new.id}/settlement/", {"action": "security", "decision": "returned", "method": "cash"}
    )
    s = P.settlement(new)
    assert (s["held"], s["from_security"], s["returned"], s["still_due"]) == (D(21000), D(5000), D(16000), 0)


def test_security_kept_needs_a_reason(staff, login_as):
    b = staff["branch"]
    e = staff["person"]("N2", "Junior Teacher", D(31000), keep_security=True, security_months=3, security_from=OCT)
    assert row_of(b, OCT, e)["security"] == D(10333)  # one month's salary in 3 parts
    client = login_as(staff["director"])
    client.post("/payroll/finalise/?month=2026-10")
    e.left_on, e.status = dt.date(2026, 11, 2), "left"
    e.save()
    client.post(f"/payroll/staff/{e.id}/settlement/", {"action": "security", "decision": "kept"})
    assert not hasattr(Employee.objects.get(pk=e.pk), "security_release")
    client.post(f"/payroll/staff/{e.id}/settlement/", {"action": "security", "decision": "kept", "reason": "No notice"})
    s = P.settlement(Employee.objects.get(pk=e.pk))
    assert s["kept"] == D(10333) and s["returned"] == 0


def test_staff_form_security_only_for_payroll_rights(staff, login_as, make_user):
    director = login_as(staff["director"]).get("/staff/new/").content.decode()
    assert 'name="keep_security"' in director
    principal = login_as(make_user("principal", Scope.BRANCH, staff["branch"])).get("/staff/new/").content.decode()
    assert 'name="keep_security"' not in principal


# ---------- A pretend ZKTeco machine speaking the same protocol ----------
def encode_time(t):
    return pack("<I", ((((t.year - 2000) * 12 + t.month - 1) * 31 + t.day - 1) * 24 + t.hour) * 60 * 60
                + t.minute * 60 + t.second)  # fmt: skip


def fake_machine(punches, key=0):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    records = b"".join(
        pack("<H24sB4sB8s", i + 1, uid.encode().ljust(24, b"\x00"), 0, encode_time(at), 0, b"\x00" * 8)
        for i, (uid, at) in enumerate(punches)
    )
    log = pack("<I", len(records)) + records

    def reply(conn, command, reply_id, data=b""):
        conn.sendall(zk.packet(command, 77, reply_id, data))

    def serve():
        conn, _a = server.accept()
        with conn:
            authed = key == 0
            while True:
                head = conn.recv(8)
                if not head:
                    break
                _m1, _m2, length = unpack("<HHI", head)
                body = b""
                while len(body) < length:
                    body += conn.recv(length - len(body))
                command, _c, _s, rid = unpack("<4H", body[:8])
                data = body[8:]
                if command == zk.CMD_CONNECT:
                    reply(conn, zk.CMD_ACK_OK if authed else zk.CMD_ACK_UNAUTH, rid)
                elif command == zk.CMD_AUTH:
                    authed = data == zk.comm_key(key, 77)
                    reply(conn, zk.CMD_ACK_OK if authed else zk.CMD_ACK_UNAUTH, rid)
                elif command == zk.CMD_GET_TIME:
                    reply(conn, zk.CMD_ACK_OK, rid, encode_time(dt.datetime(2026, 11, 5, 9, 0)))
                elif command == zk.CMD_GET_FREE_SIZES:
                    fields = [0] * 20
                    fields[4], fields[8] = 2, len(punches)
                    reply(conn, zk.CMD_ACK_OK, rid, pack("<20i", *fields))
                elif command == zk.CMD_PREPARE_BUFFER:
                    reply(conn, zk.CMD_ACK_OK, rid, b"\x00" + pack("<I", len(log)))
                elif command == zk.CMD_READ_BUFFER:
                    start, size = unpack("<ii", data)
                    part = log[start : start + size]
                    reply(conn, zk.CMD_PREPARE_DATA, rid, pack("<I", len(part)))
                    for i in range(0, len(part), 100):
                        reply(conn, zk.CMD_DATA, rid, part[i : i + 100])
                    reply(conn, zk.CMD_ACK_OK, rid)
                elif command == zk.CMD_EXIT:
                    reply(conn, zk.CMD_ACK_OK, rid)
                    break
                else:
                    reply(conn, zk.CMD_ACK_OK, rid)
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return server.getsockname()[1], thread


def test_attendance_machine_read(staff, login_as):
    g = staff["guard"]
    g.machine_id = "17"
    g.save()
    day = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=1)
    port, thread = fake_machine(
        [("17", day.replace(hour=7, minute=55)), ("17", day.replace(hour=14, minute=5)), ("99", day.replace(hour=8))],
        key=1234,
    )
    client = login_as(staff["director"])
    client.post("/staff/attendance/machines/", {"action": "save", "name": "Gate", "host": "127.0.0.1", "port": port,
                                                "comm_key": "1234", "auto_read": "on"})  # fmt: skip
    machine = AttendanceMachine.objects.get()
    client.post("/staff/attendance/machines/", {"action": "read", "machine": machine.id})
    thread.join(5)
    machine.refresh_from_db()
    assert machine.last_ok and "2 new punches" in machine.last_result and machine.unknown_ids == {"99": 1}
    assert Punch.objects.filter(employee=g).count() == 2
    page = client.get("/staff/attendance/machines/").content.decode()
    assert "99 (1)" in page and "Get attendance now" in page


def test_machine_that_does_not_answer(staff, login_as):
    client = login_as(staff["director"])
    client.post("/staff/attendance/machines/", {"action": "save", "host": "127.0.0.1", "port": "1", "comm_key": "0"})
    machine = AttendanceMachine.objects.get()
    client.post("/staff/attendance/machines/", {"action": "read", "machine": machine.id})
    machine.refresh_from_db()
    assert not machine.last_ok and machine.last_result


def test_sell_tickets_once_and_search_box_empty(org, make_user, login_as):
    from apps.academics.models import ClassLevel, Section
    from apps.events.models import Event, EventClass, TicketSale
    from apps.people.models import Enrolment, Student

    branch = org["samanabad"]
    level = ClassLevel.objects.get(code="class-3")
    section = Section.objects.create(branch=branch, session=org["session"], class_level=level, name="Rose")
    kid = Student.objects.create(branch=branch, admission_no="1398", first_name="Sami", gender="male",
                                 admission_date=dt.date(2026, 4, 1))  # fmt: skip
    Enrolment.objects.create(branch=branch, student=kid, session=org["session"], section=section)
    director = make_user("branch_owner", Scope.BRANCH, branch)
    event = Event.objects.create(branch=branch, name="Trip", date=dt.date(2026, 12, 1), created_by=director)
    EventClass.objects.create(branch=branch, event=event, class_level=level, price=1000)
    client = login_as(director)
    page = client.get(f"/events/{event.id}/sell/?q=1398").content.decode()
    assert 'name="q" value=""' in page and "Sami" in page  # the box is ready for the next number
    client.post(f"/events/{event.id}/sell/", {"student": kid.id, "paid_by": "cash"})
    client.post(f"/events/{event.id}/sell/", {"student": kid.id, "paid_by": "cash"})
    assert TicketSale.objects.count() == 1  # no second ticket
    page = client.get(f"/events/{event.id}/sell/?q=1398").content.decode()
    assert "Has a ticket" in page and "Sell again" not in page
    assert PayrollRun.objects.count() == 0
