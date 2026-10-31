"""Working out a month's pay from staff attendance (M10).

Pay = monthly salary ÷ days in the month × (days on the staff that month − unpaid days).
Unpaid days = absent days + days of unpaid leave + half of each half day, from the monthly attendance sheet
(project lead, 23 Oct 2026). Late arrivals, holidays and off days are not cut. Someone who joins or leaves
during the month is paid for the days they were on the staff. Amounts are rounded to whole rupees."""

from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction

from apps.core.models import AuditEvent
from apps.hr import services as hr

from .models import (
    Advance,
    AdvanceRecovery,
    EmployeePay,
    ManualDays,
    PayAdjustment,
    PayrollRules,
    PayrollRun,
    Payslip,
    SalaryChange,
    SalaryPayment,
)

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


def month_end(month):
    import datetime as dt

    return (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)


def bonus_applies(rules, employee):
    return rules.bonus_enabled and employee.designation in (rules.bonus_designations or [])


def _advance_plan(advances, month, left_this_month):
    """How much of each advance is due to be cut this month: a one-month advance in full, an instalment advance by
    its monthly cut (or the amount changed for this month); everything left when the person leaves this month."""
    plan = []
    for adv in advances:
        if adv.start_month > month:
            continue
        remaining = adv.remaining()
        if remaining <= 0:
            continue
        change = next((c for c in adv.month_changes.all() if c.month == month), None)
        if left_this_month:
            due = remaining
        elif change is not None:
            due = min(change.amount, remaining)
        elif adv.kind == Advance.Kind.THIS_MONTH:
            due = remaining
        else:
            due = min(adv.monthly_cut, remaining)
        if due > 0:
            plan.append((adv, due))
    return plan


def security_collected(employee):
    return (
        Payslip.objects.filter(employee=employee, run__status=PayrollRun.Status.FINAL).aggregate(
            t=models.Sum("security")
        )["t"]
        or ZERO
    )


def security_target(employee, pay, changes):
    """One month's salary, as it was in the month the security starts."""
    if not (employee.keep_security and pay):
        return ZERO
    start = employee.security_from or employee.joined_on.replace(day=1)
    return salary_for(pay, start, changes)


def _security_due(employee, pay, changes, month, collected):
    """Collected over 1-3 months from its start; what a month could not cover is cut in the next months."""
    target = security_target(employee, pay, changes)
    if not target or collected >= target:
        return ZERO
    start = employee.security_from or employee.joined_on.replace(day=1)
    if month < start:
        return ZERO
    months_in = (month.year - start.year) * 12 + month.month - start.month + 1
    per_month = _rupees(target / employee.security_months)
    due_by_now = min(target, per_month * months_in)
    return max(due_by_now - collected, ZERO)


def compute(branch, month):
    """Rows for every staff member on the staff during the month: figures, or `missing` when no salary is set.
    Figures typed in by hand for a person and month (ManualDays) replace the attendance sheet's.

    Net pay = pay for the days on the staff − absence (a day's pay per day absent, half for a half day) + bonus +
    other addition − GP Fund − EOBI − other deduction − advance − security (never below 0)."""
    dates, sheet = hr.month_sheet(branch, month)
    pays = {p.employee_id: p for p in EmployeePay.objects.filter(branch=branch)}
    manual = {m.employee_id: m for m in ManualDays.objects.filter(branch=branch, month=month)}
    extras = {a.employee_id: a for a in PayAdjustment.objects.filter(branch=branch, month=month)}
    advances = {}
    for adv in Advance.objects.filter(branch=branch).prefetch_related("month_changes").order_by("given_on", "id"):
        advances.setdefault(adv.employee_id, []).append(adv)
    rules = PayrollRules.for_branch(branch)
    changes = _changes(branch)
    last_day = month_end(month)
    rows = []
    for r in sheet:
        e = r["employee"]
        m = manual.get(e.id)
        if m:
            days_in_month, working, employed = m.days_in_month, m.working_days, m.days_employed
            absent, half = m.absent_days + m.leave_days, m.half_days
        else:
            totals = r["totals"]
            days_in_month, working = len(dates), 0
            employed = sum(1 for d in dates if e.employed_on(d))
            # Every absence is unpaid; days of unpaid leave count as absent (project lead, 31 Oct 2026).
            absent = max(totals.get("unpaid", 0), totals.get("absent", 0))
            half = totals.get("half_day", 0)
        pay = pays.get(e.id)
        row = {"employee": e, "pay": pay, "days_in_month": days_in_month, "working_days": working,
               "days_employed": employed, "absent": absent, "leave": 0, "half": half, "missing": pay is None,
               "manual": m is not None}  # fmt: skip
        if pay:
            emp_changes = changes.get(e.id, [])
            salary = salary_for(pay, month, emp_changes)
            rate = salary / days_in_month if days_in_month else ZERO
            gross = _rupees(rate * employed)
            deduction = min(_rupees(rate * (absent + Decimal(half) / 2)), gross)
            full_month = employed == days_in_month
            bonus_days = rules.bonus_days if (bonus_applies(rules, e) and full_month and not absent and not half) else 0
            bonus = _rupees(rate * bonus_days)
            x = extras.get(e.id)
            gp, eobi = (x.gp_fund, x.eobi) if x else (ZERO, ZERO)
            other_minus, other_plus = (x.other_deduction, x.other_addition) if x else (ZERO, ZERO)
            available = max(gross - deduction + bonus + other_plus - gp - eobi - other_minus, ZERO)
            left_now = bool(e.left_on and e.left_on <= last_day)
            parts = []
            for adv, due in _advance_plan(advances.get(e.id, []), month, left_now):
                take = min(due, available)
                if take > 0:
                    parts.append((adv, take))
                    available -= take
            advance = sum((t for _a, t in parts), ZERO)
            security = min(_security_due(e, pay, emp_changes, month, security_collected(e)), available)
            row.update(
                salary=salary, gross=gross, deduction=deduction, bonus_days=bonus_days, bonus=bonus, gp_fund=gp,
                eobi=eobi, other_deduction=other_minus, other_addition=other_plus,
                other_deduction_reason=x.other_deduction_reason if x else "",
                other_addition_reason=x.other_addition_reason if x else "", advance=advance, advance_parts=parts,
                security=security, net=available - security,
            )  # fmt: skip
        rows.append(row)
    return rows, _totals(rows)


def _totals(rows):
    counted = [r for r in rows if not r["missing"]]
    paid = [r for r in counted if r.get("payment")]
    net = sum((r["net"] for r in counted), ZERO)
    paid_amount = sum((r["payment"].amount for r in paid), ZERO)
    return {
        "bonus": sum((r.get("bonus", ZERO) for r in counted), ZERO),
        "advance": sum((r.get("advance", ZERO) for r in counted), ZERO),
        "security": sum((r.get("security", ZERO) for r in counted), ZERO),
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
        gross = p.net_pay + p.deduction + p.gp_fund + p.eobi + p.other_deduction + p.advance + p.security
        gross -= p.bonus + p.other_addition
        rows.append(
            {
                "employee": p.employee,
                "salary": p.monthly_salary,
                "days_in_month": p.days_in_month,
                "working_days": p.working_days,
                "days_employed": p.days_employed,
                "absent": p.absent_days + p.leave_days,
                "leave": 0,
                "half": p.half_days,
                "gross": gross,
                "deduction": p.deduction,
                "bonus_days": p.bonus_days,
                "bonus": p.bonus,
                "gp_fund": p.gp_fund,
                "eobi": p.eobi,
                "advance": p.advance,
                "security": p.security,
                "other_deduction": p.other_deduction,
                "other_addition": p.other_addition,
                "other_deduction_reason": p.other_deduction_reason,
                "other_addition_reason": p.other_addition_reason,
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
    for r in rows:
        if r["missing"]:
            continue
        slip = Payslip.objects.create(
            branch=branch,
            run=run,
            employee=r["employee"],
            designation=r["employee"].designation,
            monthly_salary=r["salary"],
            days_in_month=r["days_in_month"],
            days_employed=r["days_employed"],
            absent_days=r["absent"],
            leave_days=0,
            half_days=r["half"],
            working_days=r["working_days"],
            is_manual=r["manual"],
            method=r["pay"].method,
            deduction=r["deduction"],
            bonus_days=r["bonus_days"],
            bonus=r["bonus"],
            gp_fund=r["gp_fund"],
            eobi=r["eobi"],
            advance=r["advance"],
            security=r["security"],
            other_deduction=r["other_deduction"],
            other_deduction_reason=r["other_deduction_reason"],
            other_addition=r["other_addition"],
            other_addition_reason=r["other_addition_reason"],
            net_pay=r["net"],
            bank_name=r["pay"].bank_name,
            account_title=r["pay"].account_title,
            account_number=r["pay"].account_number,
        )
        for adv, amount in r["advance_parts"]:
            AdvanceRecovery.objects.create(
                branch=branch, advance=adv, payslip=slip, amount=amount, how=AdvanceRecovery.How.SALARY,
                on=month_end(month), recorded_by=user,
            )  # fmt: skip
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


def advances_of(employee):
    """Every advance of one person with what is cut so far and what is still due."""
    out = []
    for adv in employee.advances.prefetch_related("month_changes").order_by("-given_on", "-id"):
        recovered = adv.recovered()
        out.append({"advance": adv, "recovered": recovered, "remaining": adv.amount - recovered})
    return out


def settlement(employee):
    """What is owed either way when a person leaves (project lead, 31 Oct 2026): salaries not yet paid, the
    security held, advances still due (taken from the last salary first — that is done by the payroll — then from
    the security), and the balance."""
    unpaid = list(
        Payslip.objects.filter(employee=employee, run__status=PayrollRun.Status.FINAL, payment__isnull=True)
        .select_related("run")
        .order_by("run__month")
    )
    release = getattr(employee, "security_release", None)
    held = security_collected(employee)
    advance_due = sum((a["remaining"] for a in advances_of(employee)), ZERO)
    if release:
        from_security, returned, kept = release.for_advance, release.returned, release.kept
    else:
        from_security = min(advance_due, held)
        returned = kept = ZERO
    salary_due = sum((p.net_pay for p in unpaid), ZERO)
    return {
        "unpaid": unpaid,
        "salary_due": salary_due,
        "held": held,
        "advance_due": advance_due,
        "from_security": from_security,
        "security_left": held - from_security,
        "release": release,
        "returned": returned,
        "kept": kept,
        "to_pay": salary_due + returned,
        "still_due": max(advance_due - (0 if release else from_security), ZERO),
    }


@transaction.atomic
def release_security(employee, decision, method, reason, on, user):
    """Director or Accountant decides: return the security (left with notice) or keep it (left without notice).
    An advance still due is taken from the security first in both cases."""
    from .models import SecurityRelease

    if SecurityRelease.objects.filter(employee=employee).exists():
        raise ValueError("already decided")
    held = security_collected(employee)
    left = held
    for item in reversed(advances_of(employee)):  # oldest advance first
        if left <= 0:
            break
        take = min(item["remaining"], left)
        if take > 0:
            AdvanceRecovery.objects.create(
                branch_id=employee.branch_id, advance=item["advance"], amount=take, how=AdvanceRecovery.How.SECURITY,
                on=on, recorded_by=user, note="",
            )  # fmt: skip
            left -= take
    returned = left if decision == SecurityRelease.Decision.RETURNED else ZERO
    return SecurityRelease.objects.create(
        branch_id=employee.branch_id, employee=employee, held=held, for_advance=held - left, returned=returned,
        kept=left - returned, decision=decision, method=method if returned else "", reason=reason[:200],
        decided_on=on, decided_by=user,
    )  # fmt: skip


@transaction.atomic
def close_advance(advance, how, amount, note, on, user):
    """After leaving: money of an advance paid back by the person, or written off by management."""
    amount = min(amount, advance.remaining())
    if amount <= 0:
        raise ValueError("nothing due")
    return AdvanceRecovery.objects.create(
        branch_id=advance.branch_id, advance=advance, amount=amount, how=how, on=on, note=note[:200], recorded_by=user
    )
