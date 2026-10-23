"""M10: fixed salary, a day of absence or unpaid leave cut at salary ÷ days in the month, finalised and locked."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.accounts.models import Scope
from apps.hr.models import Employee, StaffDay
from apps.payroll import services as S
from apps.payroll.models import EmployeePay, PayrollRun

pytestmark = pytest.mark.django_db
OCT = dt.date(2026, 10, 1)
D = Decimal
SALARY = D(30000)


@pytest.fixture(autouse=True)
def november(monkeypatch):
    from django.utils import timezone

    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: dt.date(2026, 11, 5))  # October is over


@pytest.fixture
def staff(org, make_user):
    branch = org["samanabad"]
    accountant = make_user("accountant", Scope.BRANCH, branch)

    def person(code, joined=dt.date(2025, 1, 1), salary=SALARY):
        e = Employee.objects.create(
            branch=branch,
            code=code,
            full_name=f"Teacher {code}",
            gender="female",
            designation="Senior Teacher",
            staff_type="teaching",
            joined_on=joined,
        )
        if salary is not None:
            EmployeePay.objects.create(
                branch=branch, employee=e, monthly_salary=salary, bank_name="HBL", account_number="0011"
            )
        return e

    a = person("E1")
    for day, status in [(5, "absent"), (6, "absent"), (7, "leave"), (8, "half_day"), (9, "late")]:
        StaffDay.objects.create(branch=branch, employee=a, date=dt.date(2026, 10, day), status=status)
    new = person("E2", joined=dt.date(2026, 10, 17))
    unpaid = person("E3", salary=None)
    return {"branch": branch, "accountant": accountant, "a": a, "new": new, "unpaid": unpaid}


def test_absence_and_leave_are_cut_per_day(staff):
    rows, totals = S.compute(staff["branch"], OCT)
    by = {r["employee"].code: r for r in rows}
    a = by["E1"]
    assert (a["absent"], a["leave"], a["half"], a["days_in_month"]) == (2, 1, 1, 31)
    assert (a["deduction"], a["net"]) == (D(3387), D(26613))  # 30000 ÷ 31 × 3.5: half day is half, late not cut
    assert by["E2"]["days_employed"] == 15 and by["E2"]["net"] == D(14516)  # joined on the 17th
    assert by["E3"]["missing"] and totals["missing"] == 1


def test_finalise_locks_the_month_and_makes_payslips(staff, login_as):
    client = login_as(staff["accountant"])
    page = client.get("/payroll/?month=2026-10").content.decode()
    assert "26,613" in page and "Salary not set" in page and "Finalise this month" in page
    client.post("/payroll/finalise/?month=2026-10")
    run = PayrollRun.objects.get(branch=staff["branch"], month=OCT)
    assert run.payslips.count() == 2
    StaffDay.objects.create(branch=staff["branch"], employee=staff["a"], date=dt.date(2026, 10, 20), status="absent")
    assert run.payslips.get(employee=staff["a"]).net_pay == D(26613)  # locked
    pdf = client.get(f"/payroll/{run.id}/payslips.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    bank = client.get("/payroll/?month=2026-10&format=xlsx&sheet=bank")
    assert bank.status_code == 200
    client.post(f"/payroll/{run.id}/cancel/", {"reason": "Attendance corrected"})
    run.refresh_from_db()
    assert run.status == "cancelled"
    client.post("/payroll/finalise/?month=2026-10")
    assert PayrollRun.objects.get(status="final").payslips.get(employee=staff["a"]).net_pay == D(25645)


def test_current_month_cannot_be_finalised_and_who_may(staff, login_as, make_user):
    client = login_as(staff["accountant"])
    with pytest.raises(PayrollRun.DoesNotExist):
        client.post("/payroll/finalise/?month=2026-12")
        PayrollRun.objects.get(month=dt.date(2026, 12, 1))
    principal = login_as(make_user("principal", Scope.BRANCH, staff["branch"]))
    assert principal.get("/payroll/?month=2026-10").status_code == 200  # principals see payroll (23 Oct 2026)
    assert principal.post("/payroll/finalise/?month=2026-10").status_code == 403
    assert principal.post("/payroll/salaries/", {f"salary_{staff['unpaid'].id}": "20000"}).status_code == 403
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, staff["branch"]))
    assert teacher.get("/payroll/").status_code == 403


def test_salaries_page_saves_and_records(staff, login_as):
    client = login_as(staff["accountant"])
    client.post("/payroll/salaries/", {f"salary_{staff['unpaid'].id}": "25,000", f"bank_name_{staff['unpaid'].id}": ""})
    assert EmployeePay.objects.get(employee=staff["unpaid"]).monthly_salary == D(25000)
