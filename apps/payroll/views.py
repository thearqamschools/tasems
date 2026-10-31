"""Staff → Payroll (M10): salaries, the month's pay worked out from attendance, finalising, payslips, bank sheet."""

import datetime as dt
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import exports
from apps.core.branch import current_branch
from apps.diary.models import DiaryLayout
from apps.fees.models import month_start
from apps.hr.models import DESIGNATIONS, Employee

from . import services as S
from .models import (
    Advance,
    AdvanceMonth,
    AdvanceRecovery,
    EmployeePay,
    PayAdjustment,
    PayMethod,
    PayrollRules,
    PayrollRun,
    SalaryChange,
    SecurityRelease,
)


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _month(request):
    try:
        return month_start(dt.date.fromisoformat(request.GET.get("month", "") + "-01"))
    except ValueError:
        today = timezone.localdate()
        return month_start(today.replace(day=1) - dt.timedelta(days=1))  # last month: the usual one to pay


def _rows(branch, month):
    run = S.final_run(branch, month)
    rows, totals = S.run_rows(run) if run else S.compute(branch, month)
    return run, rows, totals


def _designations(rows):
    return sorted({r["employee"].designation for r in rows if r["employee"].designation})


@login_required
def index(request):
    branch = _branch(request)
    month = _month(request)
    run, rows, totals = _rows(branch, month)
    q, designation = request.GET.get("q", ""), request.GET.get("designation", "")
    shown = S.filter_rows(rows, q, designation)
    if exports.wants_xlsx(request):
        kind = request.GET.get("sheet")
        if kind == "bank" and run:
            slips = [r["slip"] for r in shown if r["slip"].method == "bank"]
            return exports.xlsx_response(
                _("Salary bank sheet") + f" {month:%b %Y}",
                [_("Code"), _("Name"), _("Bank"), _("Account title"), _("Account number / IBAN"), _("Net pay (Rs)")],
                ([p.employee.code, p.employee.full_name, p.bank_name, p.account_title, p.account_number,
                  p.net_pay] for p in slips),
                branch=branch,
            )  # fmt: skip
        return exports.xlsx_response(
            _("Payroll") + f" {month:%b %Y}",
            [_("Code"), _("Name"), _("Designation"), _("Monthly salary (Rs)"), _("Days in month"), _("Days on staff"),
             _("Absent days"), _("Unpaid leave days"), _("Half days"), _("Deduction (Rs)"), _("Net pay (Rs)"),
             _("Paid on"), _("Paid by")],
            ([r["employee"].code, r["employee"].full_name, r["employee"].designation, r.get("salary", ""),
              r["days_in_month"], r["days_employed"], r["absent"], r["leave"], r["half"], r.get("deduction", ""),
              r.get("net", _("Salary not set")), r["payment"].paid_on if r.get("payment") else "",
              r["payment"].get_method_display() if r.get("payment") else ""] for r in shown),
            branch=branch,
        )  # fmt: skip
    can = lambda perm: request.user.has_branch_perm(perm, branch.id)  # noqa: E731
    return render(
        request,
        "payroll/index.html",
        {
            "branch": branch,
            "month": month,
            "run": run,
            "rows": shown,
            "all_rows": len(rows),
            "totals": totals,
            "q": q,
            "designation": designation,
            "designations": _designations(rows),
            "can_finalise": can(S.FINALISE_PERM),
            "can_salaries": can(S.SALARY_PERM),
            "can_manual": can(S.MANUAL_PERM) and not run,
            "can_pay": can(S.PAY_PERM),
            "future": month > month_start(timezone.localdate()),
        },
    )


MANUAL_FIELDS = ("days_in_month", "working_days", "days_employed", "absent_days", "half_days")


def _number(raw, low=0, high=31):
    try:
        value = int(str(raw).strip() or 0)
    except ValueError:
        return None
    return value if low <= value <= high else None


@login_required
def manual(request):
    """Type a month's days in by hand for everyone (machine out of order, wrong sheet)."""
    branch = _branch(request, S.MANUAL_PERM)
    month = _month(request)
    if S.final_run(branch, month):
        messages.error(request, _("This month is finalised. Reopen it first to change the figures."))
        return redirect(f"/payroll/?month={month:%Y-%m}")
    rows, _totals = S.compute(branch, month)
    errors = []
    if request.method == "POST":
        saved = 0
        for r in rows:
            e = r["employee"]
            if request.POST.get(f"use_{e.id}") != "1":
                continue
            fields = {name: _number(request.POST.get(f"{name}_{e.id}")) for name in MANUAL_FIELDS}
            if None in fields.values() or not fields["days_in_month"] or fields["days_in_month"] < 28:
                errors.append(e.full_name)
                continue
            fields["leave_days"] = 0  # every absence is unpaid: one "Absent" figure (project lead, 31 Oct 2026)
            lost = fields["absent_days"] + fields["half_days"]
            if fields["days_employed"] > fields["days_in_month"] or lost > fields["days_employed"]:
                errors.append(e.full_name)
                continue
            S.save_manual(branch, month, e, fields, request.user)
            saved += 1
        if errors:
            messages.error(request, _("Check the days of: %(n)s") % {"n": ", ".join(errors)})
        if saved:
            messages.success(request, _("Days entered by hand for %(n)s staff members.") % {"n": saved})
        if not errors:
            return redirect(f"/payroll/?month={month:%Y-%m}")
        rows, _totals = S.compute(branch, month)
    return render(request, "payroll/manual.html", {"branch": branch, "month": month, "rows": rows})


@login_required
def person(request, employee_id):
    """One staff member: this month's pay and payment, salary changes (increments) and the history of every month."""
    branch = _branch(request)
    employee = Employee.objects.filter(pk=employee_id, branch=branch).first()
    if employee is None:
        raise Http404
    month = _month(request)
    run, rows, _totals = _rows(branch, month)
    row = next((r for r in rows if r["employee"].id == employee.id), None)
    pay = EmployeePay.objects.filter(employee=employee).first()
    can = lambda perm: request.user.has_branch_perm(perm, branch.id)  # noqa: E731
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "pay":
            if not can(S.PAY_PERM) or not run or row is None:
                raise PermissionDenied
            method = request.POST.get("method", "")
            try:
                paid_on = dt.date.fromisoformat(request.POST.get("paid_on", ""))
            except ValueError:
                paid_on = None
            if paid_on is None or method not in PayMethod.values:
                messages.error(request, _("Give the date and how the salary was paid."))
            elif paid_on > timezone.localdate():
                messages.error(request, _("The date cannot be in the future."))
            else:
                try:
                    S.pay(row["slip"], paid_on, method, request.POST.get("reference", "").strip(), request.user)
                    messages.success(
                        request,
                        _("Salary of %(m)s paid to %(n)s: Rs %(a)s.")
                        % {"m": f"{month:%B %Y}", "n": employee.full_name, "a": f"{row['net']:,.0f}"},
                    )
                except ValueError:
                    messages.error(request, _("This salary is already paid."))
        elif action == "extras":
            if not can("payroll.add_payadjustment") or run:
                raise PermissionDenied
            values = {}
            try:
                for name in ("gp_fund", "eobi", "other_deduction", "other_addition"):
                    raw = request.POST.get(name, "").replace(",", "").strip() or "0"
                    values[name] = Decimal(raw)
                    if values[name] < 0:
                        raise InvalidOperation
            except InvalidOperation:
                messages.error(request, _("Amounts must be numbers of 0 or more."))
            else:
                values["other_deduction_reason"] = request.POST.get("other_deduction_reason", "").strip()[:120]
                values["other_addition_reason"] = request.POST.get("other_addition_reason", "").strip()[:120]
                PayAdjustment.objects.update_or_create(
                    branch=branch, employee=employee, month=month, defaults={**values, "entered_by": request.user}
                )
                messages.success(request, _("Amounts for %(m)s saved.") % {"m": f"{month:%B %Y}"})
        elif action == "instalment":
            if not can("payroll.change_advance") or run:
                raise PermissionDenied
            adv = Advance.objects.filter(pk=request.POST.get("advance"), employee=employee).first()
            try:
                amount = Decimal(request.POST.get("amount", "").replace(",", "").strip())
                if amount < 0 or adv is None:
                    raise InvalidOperation
            except InvalidOperation:
                messages.error(request, _("Give the amount to cut this month (0 to skip)."))
            else:
                AdvanceMonth.objects.update_or_create(
                    advance=adv, month=month, defaults={"amount": amount, "branch": branch}
                )
                messages.success(request, _("This month's instalment set to Rs %(a)s.") % {"a": f"{amount:,.0f}"})
        elif action == "increment":
            if not can(S.INCREMENT_PERM) or pay is None:
                raise PermissionDenied
            try:
                from_month = month_start(dt.date.fromisoformat(request.POST.get("from_month", "") + "-01"))
                amount = Decimal(request.POST.get("new_salary", "").replace(",", "").strip())
                if amount < 0:
                    raise InvalidOperation
            except (ValueError, InvalidOperation):
                messages.error(request, _("Give the month and the new monthly salary."))
            else:
                change = S.add_increment(
                    pay, from_month, amount, request.POST.get("reason", "").strip(),
                    request.POST.get("approved_by", "").strip(), request.user,
                )  # fmt: skip
                messages.success(
                    request,
                    _("New salary Rs %(a)s from %(m)s saved.")
                    % {"a": f"{change.new_salary:,.0f}", "m": f"{from_month:%B %Y}"},
                )
        return redirect(f"{request.path}?month={month:%Y-%m}")
    return render(
        request,
        "payroll/person.html",
        {
            "branch": branch,
            "employee": employee,
            "month": month,
            "run": run,
            "row": row,
            "pay": pay,
            "history": S.history(employee),
            "changes": employee.salary_changes.select_related("recorded_by").order_by("-from_month", "-id"),
            "extras": PayAdjustment.objects.filter(employee=employee, month=month).first(),
            "advances": S.advances_of(employee),
            "security": {
                "target": S.security_target(employee, pay, list(employee.salary_changes.order_by("from_month", "id"))),
                "collected": S.security_collected(employee),
            },
            "can_extras": can("payroll.add_payadjustment") and not run,
            "can_instalment": can("payroll.change_advance") and not run,
            "left": employee.status != Employee.Status.ACTIVE or employee.left_on is not None,
            "methods": PayMethod.choices,
            "today": timezone.localdate(),
            "can_pay": can(S.PAY_PERM),
            "can_increment": can(S.INCREMENT_PERM) and pay is not None,
        },
    )


@login_required
def acknowledgement(request):
    """Salary acknowledgement sheet: a page per designation group, with a signature column (A4 PDF)."""
    from weasyprint import HTML

    branch = _branch(request)
    month = _month(request)
    run, rows, totals = _rows(branch, month)
    groups = []
    for name, _members in S.GROUPS:
        members = [r for r in rows if not r["missing"] and S.group_of(r["employee"].designation) == name]
        if members:
            groups.append({"name": name, "rows": members, "net": sum(r["net"] for r in members)})
    if not groups:
        raise Http404
    html = render_to_string(
        "payroll/acknowledgement_document.html",
        {
            "branch": branch,
            "month": month,
            "run": run,
            "groups": groups,
            "totals": totals,
            "layout": DiaryLayout.current(),
            "font_base": f"file://{settings.BASE_DIR}/static/fonts/",
            "media_base": f"file://{settings.MEDIA_ROOT}/",
            "printed": timezone.localtime(),
        },  # fmt: skip
    )
    response = HttpResponse(
        HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(), content_type="application/pdf"
    )
    response["Content-Disposition"] = f'inline; filename="Salary acknowledgement {month:%Y-%m}.pdf"'
    return response


@login_required
@require_POST
def finalise(request):
    branch = _branch(request, S.FINALISE_PERM)
    month = _month(request)
    if month >= month_start(timezone.localdate()):
        messages.error(request, _("A month can be finalised once it is over."))
    else:
        try:
            run = S.finalise(branch, month, request.user)
        except ValueError:
            messages.error(request, _("This month is already finalised."))
        else:
            messages.success(
                request,
                _("Payroll for %(m)s finalised: %(n)s payslips.") % {"m": f"{month:%B %Y}", "n": run.payslips.count()},
            )
    return redirect(f"/payroll/?month={month:%Y-%m}")


@login_required
@require_POST
def cancel(request, run_id):
    branch = _branch(request, S.FINALISE_PERM)
    run = PayrollRun.objects.filter(pk=run_id, branch=branch, status=PayrollRun.Status.FINAL).first()
    if run is None:
        raise Http404
    reason = request.POST.get("reason", "").strip()
    if run.payslips.filter(payment__isnull=False).exists():
        messages.error(request, _("Salaries of this month are already paid to some staff; it cannot be reopened."))
    elif not reason:
        messages.error(request, _("Give a reason for reopening the month."))
    else:
        S.cancel(run, request.user, reason)
        messages.success(request, _("The month is open again; its payslips are kept as cancelled."))
    return redirect(f"/payroll/?month={run.month:%Y-%m}")


@login_required
def payslips_pdf(request, run_id):
    from weasyprint import HTML

    branch = _branch(request)
    run = PayrollRun.objects.filter(pk=run_id, branch=branch).first()
    if run is None:
        raise Http404
    slips = run.payslips.select_related("employee")
    employee_id = request.GET.get("employee", "")
    if employee_id.isdigit():
        slips = slips.filter(employee_id=int(employee_id))
    if not slips:
        raise Http404
    html = render_to_string(
        "payroll/payslips_document.html",
        {
            "run": run,
            "branch": branch,
            "slips": slips,
            "layout": DiaryLayout.current(),
            "font_base": f"file://{settings.BASE_DIR}/static/fonts/",
            "media_base": f"file://{settings.MEDIA_ROOT}/",
        },
    )
    response = HttpResponse(
        HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(), content_type="application/pdf"
    )
    response["Content-Disposition"] = f'inline; filename="Payslips {run.month:%Y-%m}.pdf"'
    return response


@login_required
def salaries(request):
    branch = _branch(request)
    can_edit = request.user.has_branch_perm(S.SALARY_PERM, branch.id)
    staff = list(
        Employee.objects.filter(branch=branch, status=Employee.Status.ACTIVE).order_by("staff_type", "full_name")
    )
    designations = sorted({e.designation for e in staff if e.designation})
    q, designation = request.GET.get("q", "").strip(), request.GET.get("designation", "")
    shown = [
        e
        for e in staff
        if (not q or q.lower() in e.full_name.lower() or q.lower() == e.code.lower())
        and (not designation or e.designation == designation)
    ]
    pays = {p.employee_id: p for p in EmployeePay.objects.filter(branch=branch)}
    has_changes = set(SalaryChange.objects.filter(branch=branch).values_list("employee_id", flat=True))
    errors = []
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        changed = 0
        this_month = month_start(timezone.localdate())
        for e in shown:
            raw = request.POST.get(f"salary_{e.id}", "").replace(",", "").strip()
            method = request.POST.get(f"method_{e.id}", PayMethod.CASH)
            method = method if method in PayMethod.values else PayMethod.CASH
            fields = {k: request.POST.get(f"{k}_{e.id}", "").strip()[:n] for k, n in
                      (("bank_name", 80), ("account_title", 120), ("account_number", 40))}  # fmt: skip
            if method != PayMethod.BANK:
                fields = dict.fromkeys(fields, "")
            if not raw:
                continue
            try:
                amount = Decimal(raw)
                if amount < 0:
                    raise InvalidOperation
            except InvalidOperation:
                errors.append(e.full_name)
                continue
            pay = pays.get(e.id)
            if pay is None:
                EmployeePay.objects.create(branch=branch, employee=e, monthly_salary=amount, method=method, **fields)
                changed += 1
                continue
            if pay.monthly_salary != amount and e.id in has_changes:
                # With increments on record, a new amount here is a change from this month (kept in the history).
                S.add_increment(pay, this_month, amount, _("Changed on the Salaries page"), "", request.user)
                pay.refresh_from_db()
                changed += 1
            if (
                pay.monthly_salary != amount
                or pay.method != method
                or any(getattr(pay, k) != v for k, v in fields.items())
            ):
                pay.monthly_salary, pay.method = amount, method
                for k, v in fields.items():
                    setattr(pay, k, v)
                pay.save()  # the change is in the history with who made it
                changed += 1
        if errors:
            messages.error(request, _("Not a valid amount for: %(n)s") % {"n": ", ".join(errors)})
        messages.success(request, _("%(n)s salaries saved.") % {"n": changed})
        return redirect(request.get_full_path())
    return render(
        request,
        "payroll/salaries.html",
        {
            "rows": [(e, pays.get(e.id)) for e in shown],
            "can_edit": can_edit,
            "branch": branch,
            "methods": PayMethod.choices,
            "q": q,
            "designation": designation,
            "designations": designations,
        },
    )


@login_required
def rules(request):
    """Setup → Payroll rules: the attendance bonus and who gets it (project lead, 31 Oct 2026)."""
    branch = _branch(request)
    can_edit = request.user.has_branch_perm("payroll.change_payrollrules", branch.id)
    current = PayrollRules.for_branch(branch)
    designations = [d for d, _label in DESIGNATIONS]
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        try:
            days = max(min(int(request.POST.get("bonus_days") or 1), 5), 0)
        except ValueError:
            days = 1
        current.bonus_enabled = request.POST.get("bonus_enabled") == "on"
        current.bonus_days = days
        current.bonus_designations = [d for d in request.POST.getlist("bonus_designations") if d in designations]
        current.save()
        messages.success(request, _("Payroll rules saved."))
        return redirect("payroll:rules")
    return render(
        request,
        "payroll/rules.html",
        {"branch": branch, "rules": current, "designations": DESIGNATIONS, "can_edit": can_edit},
    )


@login_required
def advances(request):
    """All advances of the branch with what is still due, and giving a new one."""
    branch = _branch(request)
    can_add = request.user.has_branch_perm("payroll.add_advance", branch.id)
    staff = Employee.objects.filter(branch=branch).order_by("full_name")
    if request.method == "POST":
        if not can_add:
            raise PermissionDenied
        employee = staff.filter(pk=request.POST.get("employee")).first()
        kind = request.POST.get("kind", Advance.Kind.THIS_MONTH)
        method = request.POST.get("method", PayMethod.CASH)
        try:
            amount = Decimal(request.POST.get("amount", "").replace(",", "").strip())
            cut = Decimal(request.POST.get("monthly_cut", "").replace(",", "").strip() or "0")
            given_on = dt.date.fromisoformat(request.POST.get("given_on", ""))
            start = month_start(dt.date.fromisoformat(request.POST.get("start_month", "") + "-01"))
            if employee is None or amount <= 0 or cut < 0 or kind not in Advance.Kind.values:
                raise ValueError
            if kind == Advance.Kind.INSTALMENTS and cut <= 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(
                request, _("Choose the staff member and give the amount, dates and (for instalments) the monthly cut.")
            )
            return redirect("payroll:advances")
        upload = request.FILES.get("application")
        if upload and (
            upload.size > 5 * 1024 * 1024 or not upload.name.lower().endswith((".jpg", ".jpeg", ".png", ".pdf"))
        ):
            messages.error(request, _("The application must be a JPG, PNG or PDF of up to 5 MB."))
            return redirect("payroll:advances")
        adv = Advance.objects.create(
            branch=branch, employee=employee, kind=kind, amount=amount, given_on=given_on, start_month=start,
            monthly_cut=cut if kind == Advance.Kind.INSTALMENTS else 0,
            method=method if method in PayMethod.values else PayMethod.CASH,
            approved_by=request.POST.get("approved_by", "").strip()[:120],
            reason=request.POST.get("reason", "").strip()[:200], application=upload or "", recorded_by=request.user,
        )  # fmt: skip
        messages.success(
            request, _("Advance of Rs %(a)s to %(n)s saved.") % {"a": f"{adv.amount:,.0f}", "n": employee.full_name}
        )
        return redirect("payroll:advances")
    rows = []
    for adv in Advance.objects.filter(branch=branch).select_related("employee", "recorded_by"):
        recovered = adv.recovered()
        rows.append({"advance": adv, "recovered": recovered, "remaining": adv.amount - recovered})
    show = request.GET.get("show", "due")
    shown = [r for r in rows if show == "all" or r["remaining"] > 0]
    return render(
        request,
        "payroll/advances.html",
        {
            "branch": branch,
            "rows": shown,
            "show": show,
            "total_due": sum((r["remaining"] for r in rows), Decimal("0")),
            "staff": staff.filter(status=Employee.Status.ACTIVE),
            "kinds": Advance.Kind.choices,
            "methods": PayMethod.choices,
            "today": timezone.localdate(),
            "can_add": can_add,
        },
    )


@login_required
def advance_application(request, advance_id):
    branch = _branch(request)
    adv = Advance.objects.filter(pk=advance_id, branch=branch).first()
    if adv is None or not adv.application:
        raise Http404
    return FileResponse(adv.application.open("rb"), filename=f"Advance application {adv.employee.full_name}")


@login_required
def settlement(request, employee_id):
    """Final settlement of a person who leaves: unpaid salary, security returned or kept, advance still due."""
    branch = _branch(request)
    employee = Employee.objects.filter(pk=employee_id, branch=branch).first()
    if employee is None:
        raise Http404
    can_decide = request.user.has_branch_perm("payroll.add_securityrelease", branch.id)
    if request.method == "POST":
        if not can_decide:
            raise PermissionDenied
        action = request.POST.get("action")
        today = timezone.localdate()
        if action == "security":
            decision = request.POST.get("decision")
            reason = request.POST.get("reason", "").strip()
            if decision not in SecurityRelease.Decision.values or (decision == "kept" and not reason):
                messages.error(request, _("Choose return or not; give the reason when it is not returned."))
            else:
                try:
                    S.release_security(
                        employee, decision, request.POST.get("method", PayMethod.CASH), reason, today, request.user
                    )
                    messages.success(request, _("Security decision saved."))
                except ValueError:
                    messages.error(request, _("The security decision is already made."))
        elif action in (AdvanceRecovery.How.PAID_BACK, AdvanceRecovery.How.WRITTEN_OFF):
            adv = Advance.objects.filter(pk=request.POST.get("advance"), employee=employee).first()
            note = request.POST.get("note", "").strip()
            try:
                amount = Decimal(request.POST.get("amount", "").replace(",", "").strip())
                if adv is None or amount <= 0 or not note:
                    raise InvalidOperation
                S.close_advance(adv, action, amount, note, today, request.user)
                messages.success(request, _("Saved."))
            except (InvalidOperation, ValueError):
                messages.error(request, _("Give the amount and a note (who decided, how it was paid)."))
        return redirect("payroll:settlement", employee_id=employee.id)
    return render(
        request,
        "payroll/settlement.html",
        {
            "branch": branch,
            "employee": employee,
            "s": S.settlement(employee),
            "advances": S.advances_of(employee),
            "methods": PayMethod.choices,
            "decisions": SecurityRelease.Decision.choices,
            "can_decide": can_decide,
            "printed": timezone.localtime(),
        },
    )
