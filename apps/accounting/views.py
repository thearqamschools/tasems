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


# --- Other income, opening balances, cash & bank book, profit & loss (M9) -------------------

INCOME_ADD, INCOME_CANCEL = "accounting.add_income", "accounting.change_income"
OPENING_PERM = "accounting.add_openingbalance"


def _dates(request):
    """From–to dates (default: this month so far); at most one year."""
    today = timezone.localdate()

    def read(name, default):
        try:
            return dt.date.fromisoformat(request.GET.get(name, ""))
        except ValueError:
            return default

    start = read("from", today.replace(day=1))
    end = read("to", today)
    if end < start:
        start, end = end, start
    if (end - start).days > 366:
        end = start + dt.timedelta(days=366)
    return start, end


@login_required
def incomes(request):
    from .models import Income

    branch = _branch(request)
    month = _month(request)
    items = list(
        Income.objects.filter(branch=branch, date__gte=month, date__lt=add_months(month, 1)).select_related(
            "head", "bank", "recorded_by"
        )
    )
    live = [i for i in items if not i.is_cancelled]
    by_head = defaultdict(lambda: ZERO)
    for i in live:
        by_head[i.head.name] += i.amount
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Other income") + f" {month:%b %Y}",
            [_("Date"), _("Income head"), _("What for"), _("Received from"), _("Received in"), _("Reference"),
             _("Recorded by"), _("Amount (Rs)"), _("Cancelled")],
            (
                [i.date, i.head.name, i.description, i.received_from, i.received_in_label, i.reference,
                 i.recorded_by.get_full_name() or i.recorded_by.username, i.amount,
                 i.cancel_reason or _("Yes") if i.is_cancelled else ""]
                for i in items
            ),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "accounting/incomes.html",
        {
            "branch": branch,
            "month": month,
            "items": items,
            "total": sum((i.amount for i in live), ZERO),
            "by_head": sorted(by_head.items(), key=lambda kv: -kv[1]),
            "can_add": request.user.has_branch_perm(INCOME_ADD, branch.id),
            "can_cancel": request.user.has_branch_perm(INCOME_CANCEL, branch.id),
        },
    )


@login_required
def income_new(request):
    from .forms import IncomeForm
    from .models import Income

    branch = _branch(request, INCOME_ADD)
    form = IncomeForm(
        request.POST or None,
        initial={"date": timezone.localdate(), "received_in": Income.ReceivedIn.CASH},
        branch=branch,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.recorded_by = request.user
        item.save()
        messages.success(request, _("Income of Rs %(a)s recorded.") % {"a": rupees(item.amount)})
        return redirect("accounting:incomes")
    return render(request, "accounting/income_form.html", {"form": form})


@login_required
@require_POST
def income_cancel(request, pk):
    from .models import Income

    branch = _branch(request, INCOME_CANCEL)
    item = Income.objects.filter(pk=pk, branch=branch, is_cancelled=False).first()
    if item is None:
        raise Http404
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, _("Give a reason for cancelling."))
    else:
        item.is_cancelled, item.cancelled_by, item.cancel_reason = True, request.user, reason[:200]
        item.save()
        messages.success(request, _("Income cancelled. The record is kept with your reason."))
    return redirect(f"/expenses/income/?month={item.date:%Y-%m}")


@login_required
def cash_book(request):
    from . import books
    from .forms import OpeningBalanceForm
    from .models import OpeningBalance

    branch = _branch(request)
    accounts = books.accounts(branch)
    keys = {k: (label, bank) for k, label, bank in accounts}
    key = request.GET.get("account") if request.GET.get("account") in keys else "cash"
    start, end = _dates(request)
    can_open = request.user.has_branch_perm(OPENING_PERM, branch.id)
    form = OpeningBalanceForm(request.POST or None, accounts=accounts, initial={"account": key, "as_of": start})
    if request.method == "POST":
        if not can_open:
            raise PermissionDenied
        if form.is_valid():
            d = form.cleaned_data
            bank = keys[d["account"]][1]
            OpeningBalance.objects.update_or_create(
                branch=branch,
                bank=bank,
                as_of=d["as_of"],
                defaults={"amount": d["amount"], "recorded_by": request.user},
            )
            messages.success(request, _("Opening balance saved."))
            return redirect(f"/expenses/book/?account={d['account']}&from={d['as_of']}")
    data = books.book(branch, key, start, end)
    if exports.wants_xlsx(request):
        rows = [[start, _("Opening balance"), "", "", data["opening"]]]
        rows += [[x["date"], x["text"], x["in"] or "", x["out"] or "", x["balance"]] for x in data["lines"]]
        rows += [[end, _("Closing balance"), data["total_in"], data["total_out"], data["closing"]]]
        return exports.xlsx_response(
            f"{keys[key][0]} {start:%d-%m-%Y} to {end:%d-%m-%Y}",
            [_("Date"), _("Particulars"), _("Received (Rs)"), _("Paid (Rs)"), _("Balance (Rs)")],
            rows,
            branch=branch,
        )
    return render(
        request,
        "accounting/book.html",
        {
            "branch": branch,
            "accounts": accounts,
            "key": key,
            "account_label": keys[key][0],
            "start": start,
            "end": end,
            "book": data,
            "form": form if can_open and key != "online" else None,
        },
    )


@login_required
def profit_loss(request):
    from . import books

    branch = _branch(request)
    start, end = _dates(request)
    data = books.profit_and_loss(branch, start, end)
    if exports.wants_xlsx(request):
        rows = [[_("Fees received"), data["fees_total"]]]
        rows += [[r["head__name"], r["t"]] for r in data["incomes"]]
        rows += [[_("Total income"), data["total_income"]], ["", ""]]
        rows += [[r["head__name"], -r["t"]] for r in data["expenses"]]
        rows += [[_("Total expenses"), -data["total_expenses"]], [_("Surplus / deficit"), data["net"]]]
        return exports.xlsx_response(
            _("Profit and loss") + f" {start:%d-%m-%Y} to {end:%d-%m-%Y}",
            [_("Item"), _("Amount (Rs)")],
            rows,
            branch=branch,
        )
    multi = len(request.user.accessible_branch_ids(VIEW_PERM)) > 1
    return render(
        request,
        "accounting/profit_loss.html",
        {"branch": branch, "start": start, "end": end, "pl": data, "multi": multi},
    )


@login_required
def branches_statement(request):
    from . import books

    ids = request.user.accessible_branch_ids(VIEW_PERM)
    if len(ids) < 2:
        raise PermissionDenied
    start, end = _dates(request)
    rows, totals = books.branches_statement(ids, start, end)
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Income and expenses by branch") + f" {start:%d-%m-%Y} to {end:%d-%m-%Y}",
            [_("Branch"), _("Fees received (Rs)"), _("Other income (Rs)"), _("Total income (Rs)"), _("Expenses (Rs)"),
             _("Surplus / deficit (Rs)")],
            [*([r["branch"].name, r["fees"], r["other"], r["income"], r["expenses"], r["net"]] for r in rows),
             [_("Total"), totals["fees"], totals["other"], totals["income"], totals["expenses"], totals["net"]]],
        )  # fmt: skip
    return render(request, "accounting/branches.html", {"rows": rows, "totals": totals, "start": start, "end": end})
