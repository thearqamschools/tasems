"""Working out a month's pay from staff attendance (M10).

Pay = monthly salary ÷ days in the month × (days on the staff that month − unpaid days).
Unpaid days = absent days + days of unpaid leave, exactly as on the monthly attendance sheet. Half days, late
arrivals, holidays and off days are not cut. Someone who joins or leaves during the month is paid for the days
they were on the staff. Amounts are rounded to whole rupees."""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.core.models import AuditEvent
from apps.hr import services as hr

from .models import EmployeePay, PayrollRun, Payslip

ZERO = Decimal("0")
VIEW_PERM = "payroll.view_payrollrun"
SALARY_PERM = "payroll.change_employeepay"
FINALISE_PERM = "payroll.finalise_payroll"


def _rupees(value):
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def compute(branch, month):
    """Rows for every staff member on the staff during the month: figures, or `missing` when no salary is set."""
    dates, sheet = hr.month_sheet(branch, month)
    days_in_month = len(dates)
    pays = {p.employee_id: p for p in EmployeePay.objects.filter(branch=branch)}
    rows = []
    for r in sheet:
        e = r["employee"]
        totals = r["totals"]
        employed = sum(1 for d in dates if e.employed_on(d))
        absent = totals.get("absent", 0)
        leave = max(totals.get("unpaid", 0) - absent, 0)
        pay = pays.get(e.id)
        row = {"employee": e, "pay": pay, "days_in_month": days_in_month, "days_employed": employed,
               "absent": absent, "leave": leave, "missing": pay is None}  # fmt: skip
        if pay:
            rate = pay.monthly_salary / days_in_month
            gross = _rupees(rate * employed)
            deduction = _rupees(rate * (absent + leave))
            row.update(salary=pay.monthly_salary, gross=gross, deduction=deduction, net=max(gross - deduction, ZERO))
        rows.append(row)
    totals = {
        "net": sum((r["net"] for r in rows if not r["missing"]), ZERO),
        "deduction": sum((r["deduction"] for r in rows if not r["missing"]), ZERO),
        "staff": sum(1 for r in rows if not r["missing"]),
        "missing": sum(1 for r in rows if r["missing"]),
    }
    return rows, totals


def final_run(branch, month):
    return PayrollRun.objects.filter(branch=branch, month=month, status=PayrollRun.Status.FINAL).first()


@transaction.atomic
def finalise(branch, month, user):
    """Locks the month: payslips keep the figures even if attendance or salaries change later."""
    if final_run(branch, month):
        raise ValueError("This month is already finalised.")
    rows, totals = compute(branch, month)
    run = PayrollRun.objects.create(branch=branch, month=month, finalised_by=user)
    Payslip.objects.bulk_create(
        Payslip(
            branch=branch,
            run=run,
            employee=r["employee"],
            designation=r["employee"].designation,
            monthly_salary=r["salary"],
            days_in_month=r["days_in_month"],
            days_employed=r["days_employed"],
            absent_days=r["absent"],
            leave_days=r["leave"],
            deduction=r["deduction"],
            net_pay=r["net"],
            bank_name=r["pay"].bank_name,
            account_title=r["pay"].account_title,
            account_number=r["pay"].account_number,
        )
        for r in rows
        if not r["missing"]
    )
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.CREATE,
        model_label="payroll.PayrollRun",
        object_id=str(run.pk),
        object_repr=str(run),
        branch_id=branch.id,
        changes={"staff": totals["staff"], "net": str(totals["net"]), "without_salary": totals["missing"]},
    )
    return run


@transaction.atomic
def cancel(run, user, reason):
    run.status, run.cancel_reason = PayrollRun.Status.CANCELLED, reason[:200]
    run.save(update_fields=["status", "cancel_reason", "updated_at"])
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.UPDATE,
        model_label="payroll.PayrollRun",
        object_id=str(run.pk),
        object_repr=str(run),
        branch_id=run.branch_id,
        changes={"status": {"from": "final", "to": "cancelled"}, "reason": reason},
    )
