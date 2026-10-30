"""Events & Tickets (project lead, 30 Oct 2026): tickets without a voucher, receipt on the receipt printer, refunds,
expenses and the event's own profit or loss, separate from fees and the school's accounts."""

import datetime as dt
import socket
import threading
from decimal import Decimal

import pytest

from apps.academics.models import ClassLevel, Section
from apps.accounting.models import Expense
from apps.accounts.models import Scope
from apps.events.models import Event, EventExpense, TicketSale
from apps.fees.models import Payment
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(org, make_user):
    branch = org["samanabad"]
    seven = ClassLevel.objects.get(code="class-7")
    two = ClassLevel.objects.get(code="class-2")
    sec7 = Section.objects.create(
        branch=branch, session=org["session"], class_level=seven, name="Rose", gender_group="girls"
    )
    sec2 = Section.objects.create(branch=branch, session=org["session"], class_level=two, name="Daisy")

    def kid(adm, name, section, status="active"):
        s = Student.objects.create(
            branch=branch, admission_no=adm, first_name=name, gender="female", father_name="Zubair",
            admission_date=dt.date(2026, 4, 1), status=status,
        )  # fmt: skip
        Enrolment.objects.create(branch=branch, student=s, session=org["session"], section=section)
        return s

    director = make_user("branch_owner", Scope.BRANCH, branch, first_name="Demo", last_name="Director")
    return {
        "branch": branch,
        "seven": seven,
        "two": two,
        "tahrem": kid("3457", "Tahrem", sec7),
        "hadi": kid("3456", "Hadi", sec2),
        "other": kid("3458", "Ayesha", sec7),
        "director": director,
        "admin": make_user("admissions_officer", Scope.BRANCH, branch, first_name="Office", last_name="Admin"),
        "principal": make_user("principal", Scope.BRANCH, branch),
        "teacher": make_user("class_teacher", Scope.BRANCH, branch),
    }


def make_event(client, school):
    data = {
        "name": "Murree trip", "kind": "trip", "date": "2026-11-20", "venue": "Murree", "guest_price": "1500",
        "is_open": "on", f"price_{school['seven'].id}": "2500", f"price_{school['two'].id}": "2000",
    }  # fmt: skip
    answer = client.post("/events/new/", data)
    assert answer.status_code == 302, answer.content.decode()[:2000]
    return Event.objects.get(name="Murree trip")


def fake_printer(times=1):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    got = []

    def serve():
        for _ in range(times):
            conn, _addr = server.accept()
            data = bytearray()
            with conn:
                while chunk := conn.recv(65536):
                    data.extend(chunk)
            got.append(bytes(data))
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return f"127.0.0.1:{server.getsockname()[1]}", got, thread


def test_principal_makes_event_admin_sells_with_receipt(school, login_as):
    event = make_event(login_as(school["principal"]), school)
    assert {c.class_level_id: c.price for c in event.classes.all()} == {
        school["seven"].id: Decimal("2500"),
        school["two"].id: Decimal("2000"),
    }
    address, got, thread = fake_printer()
    school["branch"].receipt_printer = address
    school["branch"].save()
    admin = login_as(school["admin"])
    page = admin.get(f"/events/{event.id}/sell/?q=3457").content.decode()
    assert "Tahrem" in page and "2,500" in page
    admin.post(f"/events/{event.id}/sell/", {"student": school["tahrem"].id, "guests": "2", "paid_by": "cash"})
    thread.join(5)
    sale = TicketSale.objects.get(student=school["tahrem"])
    assert sale.amount == Decimal("5500") and sale.received_by == school["admin"] and sale.receipt_no.endswith("-0001")
    slip = got[0]
    assert b"EVENT TICKET RECEIPT" in slip and b"Murree trip" in slip and b"Tahrem" in slip
    assert b"Received by:  Office Admin" in slip and b"5,500" in slip
    # Not part of school fees or the school's expenses.
    assert not Payment.objects.exists() and not Expense.objects.exists()


def test_account_refund_expense_and_profit(school, login_as):
    event = make_event(login_as(school["director"]), school)
    director = login_as(school["director"])
    director.post(f"/events/{event.id}/sell/", {"student": school["tahrem"].id, "paid_by": "cash"})
    director.post(f"/events/{event.id}/sell/", {"student": school["hadi"].id, "paid_by": "cash"})
    director.post(f"/events/{event.id}/expenses/new/", {"head": "transport", "amount": "3000", "date": "2026-11-20"})
    page = director.get(f"/events/{event.id}/").content.decode()
    assert "4,500" in page and "3,000" in page and "1,500" in page  # collected, spent, profit
    sale = TicketSale.objects.get(student=school["hadi"])
    director.post(f"/events/{event.id}/receipts/{sale.id}/refund/", {"reason": ""})
    sale.refresh_from_db()
    assert not sale.is_refunded  # a refund needs a reason
    director.post(f"/events/{event.id}/receipts/{sale.id}/refund/", {"reason": "Ill"})
    sale.refresh_from_db()
    assert sale.is_refunded and sale.refunded_by == school["director"]
    from apps.events import services

    account = services.account(event)
    assert account["collected"] == Decimal("2500") and account["result"] == Decimal("-500") and account["refunds"] == 1
    expense = EventExpense.objects.get()
    director.post(f"/events/{event.id}/expenses/{expense.id}/cancel/", {"reason": "Typed twice"})
    assert services.account(event)["result"] == Decimal("2500")
    class_page = director.get(f"/events/{event.id}/classes/{school['seven'].id}/").content.decode()
    assert "1 of 2 students have a ticket" in class_page


def test_who_may_do_what(school, login_as):
    event = make_event(login_as(school["principal"]), school)
    assert login_as(school["principal"]).get(f"/events/{event.id}/sell/").status_code == 403  # no money
    assert login_as(school["teacher"]).get("/events/").status_code == 403
    admin = login_as(school["admin"])
    assert admin.get("/events/new/").status_code == 403
    admin.post(f"/events/{event.id}/sell/", {"student": school["tahrem"].id, "paid_by": "cash"})
    sale = TicketSale.objects.get()
    admin.post(f"/events/{event.id}/receipts/{sale.id}/refund/", {"reason": "x"})
    sale.refresh_from_db()
    assert not sale.is_refunded  # the Admin cannot refund
    # A student of a class not in the event, or who left school, gets no ticket.
    other_level = Student.objects.create(
        branch=school["branch"], admission_no="9", first_name="Left", gender="male",
        admission_date=dt.date(2026, 4, 1), status="withdrawn",
    )  # fmt: skip
    admin.post(f"/events/{event.id}/sell/", {"student": other_level.id, "paid_by": "cash"})
    assert TicketSale.objects.count() == 1


def test_parent_tree_shows_who_printed(school, login_as):
    address, got, thread = fake_printer()
    school["branch"].receipt_printer = address
    school["branch"].save()
    login_as(school["admin"]).post(f"/students/{school['tahrem'].id}/parent-tree/", HTTP_ACCEPT="application/json")
    thread.join(5)
    assert b"Printed by: Office Admin" in got[0]
