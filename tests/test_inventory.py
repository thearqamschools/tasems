"""M11: shop & stock — items, a stock ledger, the sale counter with barcode, and the money it brings in."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounting.models import Income
from apps.accounts.models import Scope
from apps.fees import services as fees
from apps.fees.models import BankAccount, Charge
from apps.inventory import services as S
from apps.inventory.models import Item, Sale, StockMove
from apps.people.models import Student

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 10, 5)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: TODAY)


@pytest.fixture
def shop(org, make_user):
    branch = org["samanabad"]
    accountant = make_user("accountant", Scope.BRANCH, branch)
    book = Item.objects.create(branch=branch, name="English reader", category="books", barcode="978100", sale_price=650)
    tie = Item.objects.create(branch=branch, name="School tie", category="uniform", barcode="T1", sale_price=250)
    S.move(book, "received", 10, TODAY, accountant, unit_cost=Decimal(500), note="Bill 12")
    S.move(tie, "received", 5, TODAY, accountant)
    student = Student.objects.create(
        branch=branch, admission_no="777", first_name="Ali", father_name="Ahmad", gender="male",
        admission_date=dt.date(2026, 4, 1),
    )  # fmt: skip
    return {"branch": branch, "accountant": accountant, "book": book, "tie": tie, "student": student}


def test_stock_is_the_sum_of_moves_and_cannot_go_below_zero(shop):
    book = shop["book"]
    S.move(book, "issue", 2, TODAY, shop["accountant"])  # quantity given as positive, stored as −2
    S.move(book, "correction", -1, TODAY, shop["accountant"], note="Counted 7")
    assert S.on_hand(shop["branch"])[book.id] == 7
    assert list(book.moves.values_list("quantity", flat=True).order_by("pk")) == [10, -2, -1]
    with pytest.raises(S.StockError):
        S.move(book, "issue", 8, TODAY, shop["accountant"])
    rows = {r["item"].name: r for r in S.stock_rows(shop["branch"])}
    assert rows["English reader"]["value"] == Decimal(650 * 7)


def test_cash_sale_takes_stock_and_records_income(shop):
    sale = S.sell(shop["branch"], [(shop["book"], 2), (shop["tie"], 1)], TODAY, "cash", shop["accountant"])
    assert sale.number == 1 and sale.total == Decimal(1550)
    assert S.on_hand(shop["branch"]) == {shop["book"].id: 8, shop["tie"].id: 4}
    income = sale.income
    assert income.amount == Decimal(1550) and income.head.code == "books" and income.received_in == "cash"
    assert S.sell(shop["branch"], [(shop["tie"], 1)], TODAY, "cash", shop["accountant"]).income.head.code == "uniform"
    with pytest.raises(S.StockError, match="School tie"):
        S.sell(shop["branch"], [(shop["tie"], 9)], TODAY, "cash", shop["accountant"])
    assert Sale.objects.count() == 2  # the refused sale left nothing behind


def test_sale_on_the_fee_account_appears_on_the_next_voucher(shop):
    student = shop["student"]
    sale = S.sell(shop["branch"], [(shop["book"], 1)], TODAY, "fees", shop["accountant"], student=student)
    assert sale.income is None and sale.charge.head.code == "others" and sale.charge.amount == Decimal(650)
    assert fees.balance(student) == Decimal(650)
    S.cancel_sale(sale, shop["accountant"], "Wrong book")
    sale.refresh_from_db()
    assert sale.is_cancelled and Charge.objects.get(pk=sale.charge_id).is_cancelled
    assert fees.balance(student) == 0 and S.on_hand(shop["branch"])[shop["book"].id] == 10
    assert sale.moves.filter(kind=StockMove.Kind.RETURN).get().quantity == 1


def test_cancelled_cash_sale_cancels_the_income(shop):
    sale = S.sell(shop["branch"], [(shop["tie"], 2)], TODAY, "cash", shop["accountant"])
    S.cancel_sale(sale, shop["accountant"], "Returned")
    assert Income.objects.get(pk=sale.income_id).is_cancelled
    S.cancel_sale(sale, shop["accountant"], "Again")  # pressing twice changes nothing
    assert S.on_hand(shop["branch"])[shop["tie"].id] == 5


def test_counter_scans_barcodes_and_completes_by_bank(shop, login_as):
    bank = BankAccount.objects.create(branch=shop["branch"], name="Askari Bank")
    client = login_as(shop["accountant"])
    client.post("/inventory/sell/", {"action": "add", "code": "978100", "qty": "2"})
    client.post("/inventory/sell/", {"action": "add", "code": "tie"})  # one match by name
    client.post("/inventory/sell/", {"action": "add", "code": "978100"})
    page = client.get("/inventory/sell/").content.decode()
    assert "English reader" in page and "School tie" in page and "2,200" in page
    missing = client.post("/inventory/sell/", {"action": "add", "code": "nothing"}, follow=True)
    assert "No item found" in missing.content.decode()
    refused = client.post("/inventory/sell/", {"action": "complete", "paid_by": "bank"}, follow=True)
    assert "Choose the bank" in refused.content.decode() and not Sale.objects.exists()
    done = client.post("/inventory/sell/", {"action": "complete", "paid_by": "bank", "bank": bank.id})
    sale = Sale.objects.get()
    assert done.url == f"/inventory/sales/{sale.id}/" and sale.total == Decimal(2200) and sale.income.bank == bank
    receipt = client.get(done.url).content.decode()
    assert "The Arqam Schools" in receipt and "English reader" in receipt
    assert "Scan or type an item to start a sale." in client.get("/inventory/sell/").content.decode()  # emptied


def test_counter_fee_account_needs_a_student(shop, login_as):
    client = login_as(shop["accountant"])
    client.post("/inventory/sell/", {"action": "add", "code": "T1"})
    page = client.post("/inventory/sell/", {"action": "complete", "paid_by": "fees"}, follow=True)
    assert "admission no." in page.content.decode() and not Sale.objects.exists()
    client.post("/inventory/sell/", {"action": "complete", "paid_by": "fees", "admission_no": "777"})
    assert Sale.objects.get().student == shop["student"]


def test_lists_reports_and_excel(shop, login_as, make_user):
    S.sell(shop["branch"], [(shop["book"], 3)], TODAY, "cash", shop["accountant"])
    principal = login_as(make_user("principal", Scope.BRANCH, shop["branch"]))
    page = principal.get("/inventory/").content.decode()
    assert "English reader" in page and "Add item" in page and 'href="/inventory/"' in page
    assert principal.get("/inventory/?format=xlsx")["Content-Type"].startswith("application/vnd.openxml")
    assert "Low stock" in principal.get("/reports/").content.decode()
    sales = principal.get("/inventory/sales/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "1,950" in sales
    assert principal.get("/inventory/sales/?from=2026-10-01&to=2026-10-31&format=xlsx&by=item").status_code == 200
    item = principal.get(f"/inventory/items/{shop['book'].id}/").content.decode()
    assert "Bill 12" in item and "Sale 1" in item


def test_item_form_and_barcode_unique(shop, login_as, make_user):
    principal = login_as(make_user("principal", Scope.BRANCH, shop["branch"]))
    data = {"name": "Pencil", "category": "stationery", "barcode": "978100", "sale_price": "20", "reorder_level": "5",
            "is_active": "on"}  # fmt: skip
    assert "already has this barcode" in principal.post("/inventory/items/new/", data).content.decode()
    data["barcode"] = "P1"
    assert principal.post("/inventory/items/new/", data).status_code == 302
    stock = principal.post(
        "/inventory/stock/",
        {
            "item": Item.objects.get(name="Pencil").id,
            "kind": "issue",
            "quantity": "3",
            "date": "2026-10-05",
        },  # fmt: skip
    )
    assert "Only 0 in stock" in stock.content.decode()


def test_permissions(shop, login_as, make_user, org):
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, shop["branch"]))
    assert teacher.get("/inventory/").status_code == 403
    assert teacher.get("/inventory/sell/").status_code == 403
    accountant = login_as(shop["accountant"])
    assert accountant.get("/inventory/items/new/").status_code == 403  # the principal keeps the item list
    sale = S.sell(shop["branch"], [(shop["tie"], 1)], TODAY, "cash", shop["accountant"])
    assert accountant.post(f"/inventory/sales/{sale.id}/cancel/", {"reason": "x"}).status_code == 403
    other = login_as(make_user("principal", Scope.BRANCH, org["lhr_franchise"]))
    assert other.get(f"/inventory/items/{shop['book'].id}/").status_code in (403, 404)
