"""M6: family vouchers — one Voucher ID for all children of a father, paid child by child."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.fees import family
from apps.fees import services as S
from apps.fees.models import FamilyVoucher, Payment, Voucher
from apps.people.models import Enrolment, Student

pytestmark = pytest.mark.django_db
OCT = dt.date(2026, 10, 1)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: dt.date(2026, 10, 5))


@pytest.fixture
def setup(org, make_user):
    branch, session = org["samanabad"], org["session"]
    section = Section.objects.create(
        branch=branch, session=session, class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    kids = []
    for n, cnic in enumerate(["3310011111111", "3310011111111", "3310022222222"]):
        s = Student.objects.create(
            branch=branch,
            admission_no=str(900 + n),
            first_name=f"Child{n}",
            father_name="Shared Father" if n < 2 else "Single Father",
            father_cnic=cnic,
            gender="male",
            admission_date=dt.date(2025 + n % 2, 4, 1),
        )
        Enrolment.objects.create(branch=branch, student=s, session=session, section=section)
        kids.append(s)
    accountant = make_user("accountant", Scope.BRANCH, branch)
    S.generate_vouchers(branch, session, OCT, OCT, dt.date(2026, 10, 10), accountant)
    return {"branch": branch, "session": session, "kids": kids, "accountant": accountant}


def test_one_family_voucher_for_brothers_and_sisters(setup):
    made, kept = family.make(setup["branch"], OCT, setup["accountant"])
    assert len(made) == 1 and kept == []  # the single child has no family voucher
    fv = made[0]
    own = [Voucher.objects.get(student=k).number for k in setup["kids"][:2]]
    assert fv.number not in own and Voucher.objects.filter(number=fv.number).count() == 0  # never the same ID
    assert fv.payable == D(4300 + 4000) and fv.items.count() == 2  # elder full fee, younger sibling fee
    again, kept = family.make(setup["branch"], OCT, setup["accountant"])
    assert again == [] and kept == [fv]  # unchanged: same number kept


def D(n):
    return Decimal(n)


def test_receiving_the_family_voucher_pays_each_child(setup, login_as):
    fv = family.make(setup["branch"], OCT, setup["accountant"])[0][0]
    client = login_as(setup["accountant"])
    page = client.get(f"/fees/family/{fv.id}/receive/").content.decode()
    assert "Child0" in page and "Child1" in page and "8,300" in page
    done = client.post(f"/fees/family/{fv.id}/receive/", {"paid_on": "2026-10-05", "how": "cash"})
    assert done.status_code == 302
    fv.refresh_from_db()
    assert fv.status == FamilyVoucher.Status.PAID
    payments = Payment.objects.filter(family_voucher=fv)
    assert sorted(p.amount for p in payments) == [D(4000), D(4300)]
    for kid in setup["kids"][:2]:
        assert S.balance(kid) == 0 and Voucher.objects.get(student=kid).status == Voucher.Status.PAID
    assert S.balance(setup["kids"][2]) == D(4300)  # the other family is untouched
    again = client.post(f"/fees/family/{fv.id}/receive/", {"paid_on": "2026-10-05", "how": "cash"})
    assert "This family voucher is paid." in again.content.decode()
    assert Payment.objects.filter(family_voucher=fv).count() == 2  # pressing again takes nothing more


def test_barcode_and_search_open_the_family_voucher(setup, login_as):
    fv = family.make(setup["branch"], OCT, setup["accountant"])[0][0]
    client = login_as(setup["accountant"])
    scanned = client.post("/fees/barcode/", {"voucher_number": str(fv.number), "paid_on": "2026-10-05", "how": "cash"})
    assert scanned.status_code == 302 and scanned.url == f"/fees/family/{fv.id}/receive/"
    assert not Payment.objects.exists()  # nothing is taken until the family page is confirmed
    found = client.get(f"/fees/?q={fv.number}")
    assert found.url == f"/fees/family/{fv.id}/receive/"


def test_list_print_and_menu(setup, login_as):
    client = login_as(setup["accountant"])
    page = client.get("/fees/family/?month=2026-10").content.decode()
    assert "Make 1 family voucher" in page and 'href="/fees/family/"' in page
    client.post("/fees/family/?month=2026-10")
    assert FamilyVoucher.objects.count() == 1
    pdf = client.get("/fees/family/print/?month=2026-10")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_changed_children_vouchers_replace_the_family_voucher(setup):
    old = family.make(setup["branch"], OCT, setup["accountant"])[0][0]
    younger = setup["kids"][1]
    S.cancel_voucher(Voucher.objects.get(student=younger), setup["accountant"], "Wrong amount")
    S.issue_voucher(younger, setup["session"], OCT, OCT, dt.date(2026, 10, 10), setup["accountant"])
    made, _kept = family.make(setup["branch"], OCT, setup["accountant"])
    old.refresh_from_db()
    assert old.status == FamilyVoucher.Status.REPLACED and made[0].number != old.number


def test_teacher_cannot_receive(setup, login_as, make_user):
    fv = family.make(setup["branch"], OCT, setup["accountant"])[0][0]
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, setup["branch"]))
    assert teacher.get(f"/fees/family/{fv.id}/receive/").status_code == 403


def test_jazzcash_file_with_a_family_voucher_id(setup, login_as):
    from tests.test_fees import _xlsx

    fv = family.make(setup["branch"], OCT, setup["accountant"])[0][0]
    client = login_as(setup["accountant"])
    rows = [["Voucher No", "Amount Paid", "Transaction Date", "TID"], [fv.number, 5000, "05/10/2026", "JC-9"]]
    wrong = client.post("/fees/payments/import/", {"step": "check", "method": "jazzcash", "file": _xlsx(rows)})
    assert "Rs 8,300 is due" in wrong.content.decode() and not wrong.context["token"]  # not split by guesswork
    rows[1][1] = 8300
    page = client.post("/fees/payments/import/", {"step": "check", "method": "jazzcash", "file": _xlsx(rows)})
    assert "Family of Shared Father" in page.content.decode()
    client.post("/fees/payments/import/", {"step": "import", "token": page.context["token"], "method": "jazzcash"})
    assert sorted(p.amount for p in Payment.objects.filter(family_voucher=fv, method="jazzcash")) == [D(4000), D(4300)]
    fv.refresh_from_db()
    assert fv.status == FamilyVoucher.Status.PAID
