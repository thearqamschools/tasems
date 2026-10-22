"""Staff → Payroll (M10): salaries, the month's pay worked out from attendance, finalising, payslips, bank sheet."""

import datetime as dt
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import exports
from apps.core.branch import current_branch
from apps.diary.models import DiaryLayout
from apps.fees.models import month_start
from apps.hr.models import Employee

from . import services as S
from .models import EmployeePay, PayrollRun


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


@login_required
def index(request):
    branch = _branch(request)
    month = _month(request)
    run = S.final_run(branch, month)
    if run:
        slips = list(run.payslips.select_related("employee"))
        rows = [
            {"employee": p.employee, "salary": p.monthly_salary, "days_in_month": p.days_in_month,
             "days_employed": p.days_employed, "absent": p.absent_days, "leave": p.leave_days,
             "deduction": p.deduction, "net": p.net_pay, "missing": False, "slip": p}
            for p in slips
        ]  # fmt: skip
        totals = {"net": sum(p.net_pay for p in slips), "deduction": sum(p.deduction for p in slips),
                  "staff": len(slips), "missing": 0}  # fmt: skip
    else:
        rows, totals = S.compute(branch, month)
    if exports.wants_xlsx(request):
        kind = request.GET.get("sheet")
        if kind == "bank" and run:
            return exports.xlsx_response(
                _("Salary bank sheet") + f" {month:%b %Y}",
                [_("Code"), _("Name"), _("Bank"), _("Account title"), _("Account number / IBAN"), _("Net pay (Rs)")],
                ([p.employee.code, p.employee.full_name, p.bank_name or _("Cash"), p.account_title, p.account_number,
                  p.net_pay] for p in run.payslips.select_related("employee")),
                branch=branch,
            )  # fmt: skip
        return exports.xlsx_response(
            _("Payroll") + f" {month:%b %Y}",
            [_("Code"), _("Name"), _("Designation"), _("Monthly salary (Rs)"), _("Days in month"), _("Days on staff"),
             _("Absent days"), _("Unpaid leave days"), _("Deduction (Rs)"), _("Net pay (Rs)")],
            ([r["employee"].code, r["employee"].full_name, r["employee"].designation, r.get("salary", ""),
              r["days_in_month"], r["days_employed"], r["absent"], r["leave"], r.get("deduction", ""),
              r.get("net", _("Salary not set"))] for r in rows),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "payroll/index.html",
        {
            "branch": branch,
            "month": month,
            "run": run,
            "rows": rows,
            "totals": totals,
            "can_finalise": request.user.has_branch_perm(S.FINALISE_PERM, branch.id),
            "can_salaries": request.user.has_branch_perm(S.SALARY_PERM, branch.id),
            "future": month > month_start(timezone.localdate()),
        },
    )


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
    if not reason:
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
    pays = {p.employee_id: p for p in EmployeePay.objects.filter(branch=branch)}
    errors = []
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        changed = 0
        for e in staff:
            raw = request.POST.get(f"salary_{e.id}", "").replace(",", "").strip()
            fields = {k: request.POST.get(f"{k}_{e.id}", "").strip()[:n] for k, n in
                      (("bank_name", 80), ("account_title", 120), ("account_number", 40))}  # fmt: skip
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
                EmployeePay.objects.create(branch=branch, employee=e, monthly_salary=amount, **fields)
                changed += 1
            elif pay.monthly_salary != amount or any(getattr(pay, k) != v for k, v in fields.items()):
                pay.monthly_salary = amount
                for k, v in fields.items():
                    setattr(pay, k, v)
                pay.save()  # the change is in the history with who made it
                changed += 1
        if errors:
            messages.error(request, _("Not a valid amount for: %(n)s") % {"n": ", ".join(errors)})
        messages.success(request, _("%(n)s salaries saved.") % {"n": changed})
        return redirect("payroll:salaries")
    return render(
        request,
        "payroll/salaries.html",
        {"rows": [(e, pays.get(e.id)) for e in staff], "can_edit": can_edit, "branch": branch},
    )
