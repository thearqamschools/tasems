"""M9: other income, cash and bank book with opening balances, profit and loss, branch-wise statement."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.accounting import books
from apps.accounting.models import Expense, ExpenseHead, Income, IncomeHead, OpeningBalance
from apps.accounts.models import Scope
from apps.fees.models import BankAccount, Payment
from apps.people.models import Student

pytestmark = pytest.mark.django_db
D = Decimal
OCT1, OCT5, OCT10 = dt.date(2026, 10, 1), dt.date(2026, 10, 5), dt.date(2026, 10, 10)


@pytest.fixture
def money(org, make_user):
    branch = org["samanabad"]
    director = make_user("branch_owner", Scope.BRANCH, branch)
    bank = BankAccount.objects.create(branch=branch, name="Askari")
    kid = Student.objects.create(branch=branch, admission_no="1", first_name="A", gender="male", admission_date=OCT1)
    pay = dict(branch=branch, student=kid, received_by=director)
    Payment.objects.create(**pay, amount=D(4300), paid_on=OCT5, method="counter")
    Payment.objects.create(**pay, amount=D(4000), paid_on=OCT5, method="bank", bank=bank)
    Payment.objects.create(**pay, amount=D(999), paid_on=OCT5, method="counter", is_reversed=True)
    Income.objects.create(
        branch=branch,
        date=OCT5,
        head=IncomeHead.objects.get(code="uniform"),
        amount=D(1500),
        description="Uniform sale",
        recorded_by=director,
    )
    Expense.objects.create(
        branch=branch,
        date=OCT5,
        head=ExpenseHead.objects.get(code="utilities"),
        amount=D(1200),
        description="Electricity",
        recorded_by=director,
    )
    Expense.objects.create(
        branch=branch,
        date=OCT5,
        head=ExpenseHead.objects.get(code="repairs"),
        amount=D(800),
        description="Fan",
        paid_from="bank",
        bank=bank,
        recorded_by=director,
    )
    return {"branch": branch, "director": director, "bank": bank}


def test_cash_book_counts_forward_from_the_opening_balance(money):
    branch = money["branch"]
    plain = books.book(branch, "cash", OCT1, OCT10)
    assert (plain["opening"], plain["total_in"], plain["total_out"], plain["closing"]) == (0, D(5800), D(1200), D(4600))
    OpeningBalance.objects.create(branch=branch, as_of=OCT1, amount=D(10000), recorded_by=money["director"])
    counted = books.book(branch, "cash", OCT1, OCT10)
    assert counted["closing"] == D(14600) and counted["opening_record"] is not None
    later = books.book(branch, "cash", dt.date(2026, 10, 6), OCT10)
    assert later["opening"] == D(14600) and later["lines"] == []
    bank = books.book(branch, f"bank:{money['bank'].id}", OCT1, OCT10)
    assert (bank["total_in"], bank["total_out"]) == (D(4000), D(800))


def test_profit_and_loss_and_page(money, login_as):
    pl = books.profit_and_loss(money["branch"], OCT1, OCT10)
    assert (pl["fees_total"], pl["other_income"], pl["total_expenses"], pl["net"]) == (
        D(8300),
        D(1500),
        D(2000),
        D(7800),
    )
    client = login_as(money["director"])
    page = client.get("/expenses/profit-loss/?from=2026-10-01&to=2026-10-10").content.decode()
    assert "7,800" in page and "Uniform sale" in page and "Fan" not in page  # totals by head, not each entry
    assert client.get("/expenses/profit-loss/?from=2026-10-01&to=2026-10-10&format=xlsx").status_code == 200


def test_income_is_recorded_and_cancelled_with_a_reason(money, login_as):
    client = login_as(money["director"])
    head = IncomeHead.objects.get(code="canteen")
    client.post(
        "/expenses/income/new/",
        {"date": "2026-10-05", "head": head.id, "amount": "700", "description": "Tuck shop", "received_in": "cash"},
    )
    item = Income.objects.get(head=head)
    assert client.post(f"/expenses/income/{item.id}/cancel/", {"reason": ""}).status_code == 302
    item.refresh_from_db()
    assert not item.is_cancelled
    client.post(f"/expenses/income/{item.id}/cancel/", {"reason": "Entered twice"})
    item.refresh_from_db()
    assert item.is_cancelled and item.cancel_reason == "Entered twice"


def test_opening_balance_from_the_page_and_who_may(money, login_as, make_user):
    client = login_as(money["director"])
    client.post("/expenses/book/", {"account": "cash", "as_of": "2026-10-01", "amount": "5000"})
    assert OpeningBalance.objects.get(branch=money["branch"], bank=None).amount == D(5000)
    accountant = login_as(make_user("accountant", Scope.BRANCH, money["branch"]))
    assert "Enter an opening balance" in accountant.get("/expenses/book/").content.decode()  # accountant: full rights
    principal = login_as(make_user("principal", Scope.BRANCH, money["branch"]))
    assert principal.get("/expenses/book/").status_code == 403  # no accounting for principals (23 Oct 2026)
    assert principal.get("/expenses/profit-loss/").status_code == 403


def test_branch_statement_for_head_office(money, login_as, make_user, org):
    admin = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"]))
    page = admin.get("/expenses/branches/?from=2026-10-01&to=2026-10-10")
    rows = page.context["rows"]
    samanabad = next(r for r in rows if r["branch"] == money["branch"])
    assert samanabad["net"] == D(7800) and all(r["branch"].head_office == org["fsd"] for r in rows)
    director = login_as(money["director"])
    assert director.get("/expenses/branches/").status_code == 403
