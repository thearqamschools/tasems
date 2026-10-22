"""Finance → Expenses: record what the branch spends, see the month by head, and today's cash in hand."""

import datetime as dt
from collections import defaultdict
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import exports
from apps.core.branch import current_branch
from apps.core.templatetags.tasems_tags import rupees
from apps.fees import reports as fee_reports
from apps.fees.models import add_months, month_start

from .forms import ExpenseForm
from .models import Expense

VIEW_PERM, ADD_PERM, CANCEL_PERM = "accounting.view_expense", "accounting.add_expense", "accounting.change_expense"
ZERO = fee_reports.ZERO


def _branch(request, perm=VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _month(request):
    try:
        return month_start(dt.date.fromisoformat(request.GET.get("month", "") + "-01"))
    except ValueError:
        return month_start(timezone.localdate())


@login_required
def index(request):
    branch = _branch(request)
    month = _month(request)
    today = timezone.localdate()
    expenses = list(
        Expense.objects.filter(branch=branch, date__gte=month, date__lt=add_months(month, 1)).select_related(
            "head", "bank", "recorded_by"
        )
    )
    live = [e for e in expenses if not e.is_cancelled]
    by_head = defaultdict(lambda: ZERO)
    for e in live:
        by_head[e.head.name] += e.amount
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Expenses") + f" {month:%b %Y}",
            [_("Date"), _("Expense head"), _("What for"), _("Paid to"), _("Paid from"), _("Reference"),
             _("Recorded by"), _("Amount (Rs)"), _("Cancelled")],
            (
                [e.date, e.head.name, e.description, e.paid_to, e.paid_from_label, e.reference,
                 e.recorded_by.get_full_name() or e.recorded_by.username, e.amount,
                 e.cancel_reason or _("Yes") if e.is_cancelled else ""]
                for e in expenses
            ),
            branch=branch,
        )  # fmt: skip
    # Today's cash in hand: cash fees received minus cash spent (bank money is not in the drawer).
    fees_today = fee_reports.collections(branch, today, today)
    cash_spent_today = sum(
        (e.amount for e in Expense.objects.filter(branch=branch, date=today, is_cancelled=False, paid_from="cash")),
        ZERO,
    )
    return render(
        request,
        "accounting/index.html",
        {
            "branch": branch,
            "month": month,
            "expenses": expenses,
            "total": sum((e.amount for e in live), ZERO),
            "cash_total": sum((e.amount for e in live if e.paid_from == "cash"), ZERO),
            "bank_total": sum((e.amount for e in live if e.paid_from == "bank"), ZERO),
            "by_head": sorted(by_head.items(), key=lambda kv: -kv[1]),
            "cash_in": fees_today["cash_total"],
            "cash_out": cash_spent_today,
            "cash_net": fees_today["cash_total"] - cash_spent_today,
            "can_add": request.user.has_branch_perm(ADD_PERM, branch.id),
            "can_cancel": request.user.has_branch_perm(CANCEL_PERM, branch.id),
        },
    )


@login_required
def new(request):
    branch = _branch(request, ADD_PERM)
    form = ExpenseForm(
        request.POST or None,
        request.FILES or None,
        initial={"date": timezone.localdate(), "paid_from": Expense.PaidFrom.CASH},
        branch=branch,
    )
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.recorded_by = request.user
        expense.save()
        messages.success(request, _("Expense of Rs %(a)s recorded.") % {"a": rupees(expense.amount)})
        return redirect("accounting:index")
    return render(request, "accounting/form.html", {"form": form})


@login_required
@require_POST
def cancel(request, pk):
    branch = _branch(request, CANCEL_PERM)
    expense = Expense.objects.filter(pk=pk, branch=branch, is_cancelled=False).first()
    reason = request.POST.get("reason", "").strip()
    if expense is None:
        raise Http404
    if not reason:
        messages.error(request, _("Give a reason for cancelling the expense."))
    else:
        expense.is_cancelled, expense.cancelled_by, expense.cancel_reason = True, request.user, reason[:200]
        expense.save()
        messages.success(request, _("Expense cancelled. The record is kept with your reason."))
    return redirect(f"/expenses/?month={expense.date:%Y-%m}")


@login_required
def attachment(request, pk):
    branch = _branch(request)
    expense = Expense.objects.filter(pk=pk, branch=branch).first()
    if expense is None or not expense.attachment:
        raise Http404
    return FileResponse(
        expense.attachment.open("rb"), filename=f"Bill {expense.date:%Y-%m-%d}{Path(expense.attachment.name).suffix}"
    )
