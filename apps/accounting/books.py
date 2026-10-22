"""Cash and bank book, profit and loss, and the branch-wise statement for head office (M9).

Money in: fee payments (Fees pages) and other income. Money out: expenses. Nothing is typed twice: the book and
the statements are worked out from those records, so they always agree with the Fees and Expenses pages.
Accounts: cash in hand, each of the branch's banks, and "online" for fees paid through JazzCash or other channels
that were not tied to one of the branch's banks."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _

from apps.fees.models import BankAccount, Method, Payment

from .models import Expense, Income, OpeningBalance

ZERO = Decimal("0")


def accounts(branch):
    """[(key, label, bank or None)]"""
    out = [("cash", _("Cash in hand"), None)]
    out += [(f"bank:{b.id}", b.name, b) for b in BankAccount.objects.filter(branch=branch).order_by("name")]
    if _online_payments(branch).exists():
        out.append(("online", _("Online (JazzCash and others, no bank chosen)"), None))
    return out


def _online_payments(branch):
    return Payment.objects.filter(branch=branch, is_reversed=False, bank__isnull=True).exclude(method=Method.COUNTER)


def _filters(branch, key):
    """(payments, incomes, expenses) querysets of one account."""
    pays = Payment.objects.filter(branch=branch, is_reversed=False)
    inc = Income.objects.filter(branch=branch, is_cancelled=False)
    exp = Expense.objects.filter(branch=branch, is_cancelled=False)
    if key == "cash":
        return pays.filter(method=Method.COUNTER), inc.filter(received_in="cash"), exp.filter(paid_from="cash")
    if key == "online":
        return _online_payments(branch), inc.none(), exp.none()
    bank_id = int(key.split(":")[1])
    return pays.filter(bank_id=bank_id), inc.filter(bank_id=bank_id), exp.filter(bank_id=bank_id)


def _net(branch, key, start=None, end=None):
    """Money in minus money out for an account between two dates (either may be open)."""

    def window(qs, field):
        if start:
            qs = qs.filter(**{f"{field}__gte": start})
        if end:
            qs = qs.filter(**{f"{field}__lte": end})
        return qs.aggregate(t=Sum("amount"))["t"] or ZERO

    pays, inc, exp = _filters(branch, key)
    return window(pays, "paid_on") + window(inc, "date") - window(exp, "date")


def opening(branch, key, start):
    """(balance at the start of `start`, opening record used or None)."""
    bank_id = None if key in ("cash", "online") else int(key.split(":")[1])
    record = (
        OpeningBalance.objects.filter(branch=branch, bank_id=bank_id, as_of__lte=start).order_by("-as_of").first()
        if key != "online"
        else None
    )
    if record:
        return record.amount + _net(branch, key, record.as_of, start - dt.timedelta(days=1)), record
    return _net(branch, key, None, start - dt.timedelta(days=1)), None


def book(branch, key, start, end):
    """The account's lines between two dates with a running balance. Fees are one line per day."""
    pays, inc, exp = _filters(branch, key)
    lines = []
    fees_by_day = (
        pays.filter(paid_on__gte=start, paid_on__lte=end)
        .values("paid_on")
        .annotate(t=Sum("amount"))
        .order_by("paid_on")
    )
    counts = defaultdict(int)
    for d in pays.filter(paid_on__gte=start, paid_on__lte=end).values_list("paid_on", flat=True):
        counts[d] += 1
    for row in fees_by_day:
        lines.append(
            {"date": row["paid_on"], "text": _("Fees received (%(n)s payments)") % {"n": counts[row["paid_on"]]},
             "kind": "fees", "in": row["t"], "out": ZERO, "order": 0}
        )  # fmt: skip
    for i in inc.filter(date__gte=start, date__lte=end).select_related("head"):
        text = f"{i.head.name}: {i.description}" + (f" ({i.received_from})" if i.received_from else "")
        lines.append({"date": i.date, "text": text, "kind": "income", "in": i.amount, "out": ZERO, "order": 1})
    for e in exp.filter(date__gte=start, date__lte=end).select_related("head"):
        text = f"{e.head.name}: {e.description}" + (f" ({e.paid_to})" if e.paid_to else "")
        lines.append({"date": e.date, "text": text, "kind": "expense", "in": ZERO, "out": e.amount, "order": 2})
    lines.sort(key=lambda x: (x["date"], x["order"]))
    balance, record = opening(branch, key, start)
    first = balance
    for line in lines:
        balance += line["in"] - line["out"]
        line["balance"] = balance
    return {
        "opening": first,
        "opening_record": record,
        "lines": lines,
        "total_in": sum((x["in"] for x in lines), ZERO),
        "total_out": sum((x["out"] for x in lines), ZERO),
        "closing": balance,
    }


def profit_and_loss(branch, start, end):
    pays = Payment.objects.filter(branch=branch, is_reversed=False, paid_on__gte=start, paid_on__lte=end)
    fees_cash = pays.filter(method=Method.COUNTER).aggregate(t=Sum("amount"))["t"] or ZERO
    fees_total = pays.aggregate(t=Sum("amount"))["t"] or ZERO
    incomes = list(
        Income.objects.filter(branch=branch, is_cancelled=False, date__gte=start, date__lte=end)
        .values("head__name")
        .annotate(t=Sum("amount"))
        .order_by("-t")
    )
    expenses = list(
        Expense.objects.filter(branch=branch, is_cancelled=False, date__gte=start, date__lte=end)
        .values("head__name")
        .annotate(t=Sum("amount"))
        .order_by("-t")
    )
    other = sum((r["t"] for r in incomes), ZERO)
    spent = sum((r["t"] for r in expenses), ZERO)
    royalty_share = branch.royalty_percent if branch.ownership == "franchise" else ZERO
    return {
        "fees_total": fees_total,
        "fees_cash": fees_cash,
        "fees_other": fees_total - fees_cash,
        "incomes": incomes,
        "other_income": other,
        "total_income": fees_total + other,
        "expenses": expenses,
        "total_expenses": spent,
        "net": fees_total + other - spent,
        "royalty_percent": royalty_share,
        "royalty_on_fees": (fees_total * royalty_share / 100).quantize(Decimal("1")) if royalty_share else ZERO,
    }


def branches_statement(branch_ids, start, end):
    """Per branch: fees received, other income, expenses, net — three grouped queries for any number of branches."""
    from apps.organisation.models import Branch

    def grouped(qs, field):
        return dict(
            qs.filter(**{f"{field}__gte": start, f"{field}__lte": end})
            .values_list("branch_id")
            .annotate(t=Sum("amount"))
        )

    fees = grouped(Payment.objects.filter(branch_id__in=branch_ids, is_reversed=False), "paid_on")
    other = grouped(Income.objects.filter(branch_id__in=branch_ids, is_cancelled=False), "date")
    spent = grouped(Expense.objects.filter(branch_id__in=branch_ids, is_cancelled=False), "date")
    rows = []
    for b in (
        Branch.objects.filter(id__in=branch_ids).select_related("head_office").order_by("head_office__name", "name")
    ):
        f, o, s = fees.get(b.id, ZERO), other.get(b.id, ZERO), spent.get(b.id, ZERO)
        rows.append({"branch": b, "fees": f, "other": o, "income": f + o, "expenses": s, "net": f + o - s})
    totals = {k: sum((r[k] for r in rows), ZERO) for k in ("fees", "other", "income", "expenses", "net")}
    return rows, totals
