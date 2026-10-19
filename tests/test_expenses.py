"""Finance → Expenses: recording, cash in hand, who may do what, private bill photos."""

import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounting.models import Expense, ExpenseHead
from apps.accounts.models import Scope
from apps.fees.models import BankAccount

pytestmark = pytest.mark.django_db


def post(**overrides):
    data = {
        "date": timezone.localdate().isoformat(),
        "head": ExpenseHead.objects.get(code="utilities").id,
        "amount": "2500",
        "description": "Electricity bill",
        "paid_to": "FESCO",
        "paid_from": "cash",
    }
    data.update(overrides)
    return data


def test_principal_records_expenses_and_sees_cash_in_hand(org, make_user, login_as, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    branch = org["samanabad"]
    principal = make_user("principal", Scope.BRANCH, branch)
    client = login_as(principal)
    bill = SimpleUploadedFile("bill.jpg", b"\xff\xd8 bill", content_type="image/jpeg")
    assert client.post("/expenses/new/", post(attachment=bill)).status_code == 302
    askari = BankAccount.objects.create(branch=branch, name="Askari Bank")
    page = client.post("/expenses/new/", post(paid_from="bank", amount="9000")).content.decode()
    assert "Choose the bank" in page
    client.post("/expenses/new/", post(paid_from="bank", bank=askari.id, amount="9000", description="Rent"))
    cash, bank = Expense.objects.get(paid_from="cash"), Expense.objects.get(paid_from="bank")
    assert cash.recorded_by == principal and cash.attachment and bank.bank == askari
    body = client.get("/expenses/").content.decode()
    assert "11,500" in body  # spent this month
    assert "-2,500" in body  # cash in hand from today: no cash fees yet, 2,500 spent in cash
    assert client.get(f"/expenses/{cash.id}/bill/").status_code == 200
    client.post(f"/expenses/{cash.id}/cancel/", {"reason": "Entered twice"})
    cash.refresh_from_db()
    assert cash.is_cancelled and cash.cancel_reason == "Entered twice"


def test_who_may_add_cancel_and_see(org, make_user, login_as):
    branch = org["samanabad"]
    accountant = login_as(make_user("accountant", Scope.BRANCH, branch))
    accountant.post("/expenses/new/", post())
    expense = Expense.objects.get()
    assert accountant.post(f"/expenses/{expense.id}/cancel/", {"reason": "x"}).status_code == 403
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, branch))
    assert teacher.get("/expenses/").status_code == 403
    outsider = login_as(make_user("principal", Scope.BRANCH, org["fsd_franchise"]))
    assert "Electricity bill" not in outsider.get("/expenses/").content.decode()
    assert outsider.get(f"/expenses/{expense.id}/bill/").status_code == 404


def test_future_dates_refused(org, make_user, login_as):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    tomorrow = timezone.localdate() + dt.timedelta(days=1)
    assert "in the future" in client.post("/expenses/new/", post(date=tomorrow.isoformat())).content.decode()
    assert not Expense.objects.exists()
