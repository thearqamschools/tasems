"""Working out a month's pay from staff attendance (M10).

Pay = monthly salary ÷ days in the month × (days on the staff that month − unpaid days).
Unpaid days = absent days + days of unpaid leave + half of each half day, from the monthly attendance sheet
(project lead, 23 Oct 2026). Late arrivals, holidays and off days are not cut. Someone who joins or leaves
during the month is paid for the days they were on the staff. Amounts are rounded to whole rupees."""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.core.models import AuditEvent
from apps.hr import services as hr

from .models import EmployeePay, ManualDays, PayrollRun, Payslip, SalaryChange, SalaryPayment

ZERO = Decimal("0")
VIEW_PERM = "payroll.view_payrollrun"
SALARY_PERM = "payroll.change_employeepay"
FINALISE_PERM = "payroll.finalise_payroll"
MANUAL_PERM = "payroll.add_manualdays"
PAY_PERM = "payroll.add_salarypayment"
INCREMENT_PERM = "payroll.add_salarychange"

# Pages of the salary acknowledgement sheet, by designation (project lead, 31 Oct 2026).
GROUPS = [
    ("Administration", ["Director", "Principal", "Vice Principal", "Coordinator", "Accountant", "Admin", "Lawyer"]),
    ("Teachers", ["Senior Teacher", "Junior Teacher", "Qari"]),
    ("Helping staff", ["Guard", "Aapa", "Janitorial staff", "Office boy", "Helping staff / Other"]),
]


def group_of(designation):
    for name, designations in GROUPS:
        if designation in designations:
            return name
    return "Helping staff"


def salary_for(pay, month, changes):
    """The monthly salary that applies to `month`: the latest change from that month or earlier; before the first
    change, the salary it started from; with no changes, the salary set now."""
    applied = [c for c in changes if c.from_month <= month]
    if applied:
        return applied[-1].new_salary
    if changes:
        return changes[0].old_salary
    return pay.monthly_salary


def _changes(branch):
    out = {}
    for c in SalaryChange.objects.filter(branch=branch).order_by("from_month", "id"):
        out.setdefault(c.employee_id, []).append(c)
    return out


def _rupees(value):
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def compute(branch, month):
    """Rows for every staff member on the staff during the month: figures, or `missing` when no salary is set.
    Figures typed in by hand for a person and month (ManualDays) replace the attendance sheet's."""
    dates, sheet = hr.month_sheet(branch, month)
    pays = {p.employee_id: p for p in EmployeePay.objects.filter(branch=branch)}
    manual = {m.employee_id: m for m in ManualDays.objects.filter(branch=branch, month=month)}
    changes = _changes(branch)
    rows = []
    for r in sheet:
        e = r["employee"]
        m = manual.get(e.id)
        if m:
            days_in_month, working, employed = m.days_in_month, m.working_days, m.days_employed
            absent, leave, half = m.absent_days, m.leave_days, m.half_days
        else:
            totals = r["totals"]
            days_in_month, working = len(dates), 0
            employed = sum(1 for d in dates if e.employed_on(d))
            absent = totals.get("absent", 0)
            leave = max(totals.get("unpaid", 0) - absent, 0)
            half = totals.get("half_day", 0)
        pay = pays.get(e.id)
        row = {"employee": e, "pay": pay, "days_in_month": days_in_month, "working_days": working,
               "days_employed": employed, "absent": absent, "leave": leave, "half": half, "missing": pay is None,
               "manual": m is not None}  # fmt: skip
        if pay:
            salary = salary_for(pay, month, changes.get(e.id, []))
            rate = salary / days_in_month if days_in_month else ZERO
            gross = _rupees(rate * employed)
            deduction = min(_rupees(rate * (absent + leave + Decimal(half) / 2)), gross)
            row.update(salary=salary, gross=gross, deduction=deduction, net=max(gross - deduction, ZERO))
        rows.append(row)
    return rows, _totals(rows)


def _totals(rows):
    counted = [r for r in rows if not r["missing"]]
    paid = [r for r in counted if r.get("payment")]
    net = sum((r["net"] for r in counted), ZERO)
    paid_amount = sum((r["payment"].amount for r in paid), ZERO)
    return {
        "salaries": sum((r["gross"] for r in counted), ZERO),
        "net": net,
        "deduction": sum((r["deduction"] for r in counted), ZERO),
        "staff": len(counted),
        "missing": sum(1 for r in rows if r["missing"]),
        "paid": paid_amount,
        "paid_staff": len(paid),
        "to_pay": net - paid_amount,
    }


def run_rows(run):
    """The rows of a finalised month, from its payslips, with each person's payment if made."""
    rows = []
    for p in run.payslips.select_related("employee", "payment", "payment__recorded_by"):
        payment = getattr(p, "payment", None)
        rows.append(
            {
                "employee": p.employee,
                "salary": p.monthly_salary,
                "days_in_month": p.days_in_month,
                "working_days": p.working_days,
                "days_employed": p.days_employed,
                "absent": p.absent_days,
                "leave": p.leave_days,
                "half": p.half_days,
                "gross": p.net_pay + p.deduction,
                "deduction": p.deduction,
                "net": p.net_pay,
                "missing": False,
                "slip": p,
                "manual": p.is_manual,
                "payment": payment,
                "method": p.method,
            }  # fmt: skip
        )
    return rows, _totals(rows)


def filter_rows(rows, q="", designation=""):
    q = q.strip().lower()
    return [
        r
        for r in rows
        if (not q or q in r["employee"].full_name.lower() or q == r["employee"].code.lower())
        and (not designation or r["employee"].designation == designation)
    ]


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
            half_days=r["half"],
            working_days=r["working_days"],
            is_manual=r["manual"],
            method=r["pay"].method,
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


@transaction.atomic
def save_manual(branch, month, employee, figures, user):
    ManualDays.objects.update_or_create(
        branch=branch, employee=employee, month=month, defaults={**figures, "entered_by": user}
    )


@transaction.atomic
def pay(payslip, paid_on, method, reference, user):
    """Records that one person's salary for a finalised month was handed over; it cannot be changed afterwards."""
    payslip = Payslip.objects.select_for_update().get(pk=payslip.pk)
    if SalaryPayment.objects.filter(payslip=payslip).exists():
        raise ValueError("already paid")
    if payslip.run.status != PayrollRun.Status.FINAL:
        raise ValueError("month not final")
    return SalaryPayment.objects.create(
        branch_id=payslip.branch_id, payslip=payslip, amount=payslip.net_pay, paid_on=paid_on, method=method,
        reference=reference[:60], recorded_by=user,
    )  # fmt: skip


@transaction.atomic
def add_increment(pay_record, from_month, new_salary, reason, approved_by, user):
    """A new salary from a month on. The salary it replaces is the one that applied in that month."""
    changes = list(SalaryChange.objects.filter(employee=pay_record.employee).order_by("from_month", "id"))
    old = salary_for(pay_record, from_month, changes)
    change = SalaryChange.objects.create(
        branch_id=pay_record.branch_id, employee=pay_record.employee, from_month=from_month, old_salary=old,
        new_salary=new_salary, reason=reason[:200], approved_by=approved_by[:120], recorded_by=user,
    )  # fmt: skip
    current = salary_for(pay_record, month_start_today(), [*changes, change])
    if pay_record.monthly_salary != current:
        pay_record.monthly_salary = current
        pay_record.save()
    return change


def month_start_today():
    from django.utils import timezone

    return timezone.localdate().replace(day=1)


def history(employee):
    """Every finalised month of one person, newest first, with what was paid."""
    return (
        Payslip.objects.filter(employee=employee, run__status=PayrollRun.Status.FINAL)
        .select_related("run", "payment")
        .order_by("-run__month")
    )
