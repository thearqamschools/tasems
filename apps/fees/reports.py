"""Read-only figures: voucher tables for printing, month summary, defaulters, collections, royalty."""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils.translation import gettext as _

from apps.people.models import StudentGuardian

from .models import Charge, FeeHead, Method, Payment, RoyaltyPayment, Voucher, add_months, month_start
from .services import ZERO

MAX_ROWS = 3


def columns():
    """Voucher columns in voucher order (Admission … Others, Fine)."""
    return list(FeeHead.objects.filter(is_active=True).order_by("sort_order"))


@dataclass
class VoucherTable:
    voucher: Voucher
    heads: list
    rows: list = field(default_factory=list)  # (label, {head_id: amount}, arrears, total)
    totals: dict = field(default_factory=dict)
    arrears: Decimal = ZERO
    total: Decimal = ZERO
    discounts: list = field(default_factory=list)  # (reason, amount)


def voucher_table(voucher, heads=None):
    heads = heads if heads is not None else columns()
    table = VoucherTable(voucher=voucher, heads=heads, arrears=voucher.arrears)
    by_month = defaultdict(lambda: defaultdict(lambda: ZERO))
    discounts = defaultdict(lambda: ZERO)
    for c in voucher.charges.filter(is_cancelled=False).select_related("head"):
        by_month[c.month][c.head_id] += c.amount
        if c.discount and c.discount_reason != "Agreed fee":  # an agreed fee is the child's fee, not a discount
            discounts[c.discount_reason or "Discount"] += c.discount
    months = sorted(by_month)
    if len(months) > MAX_ROWS:
        # Many months on one voucher (paid together): one combined row keeps every copy on its third of the page.
        cells = defaultdict(lambda: ZERO)
        for m in months:
            for head_id, amount in by_month[m].items():
                cells[head_id] += amount
        label = f"{months[0]:%b_%Y} – {months[-1]:%b_%Y}"
        table.rows.append((label, dict(cells), None, sum(cells.values(), ZERO)))
    else:
        for month in months:
            cells = by_month[month]
            table.rows.append((month.strftime("%b_%Y"), dict(cells), None, sum(cells.values(), ZERO)))
    if voucher.arrears:
        table.rows.insert(
            0, ("Previous dues" if voucher.arrears > 0 else "Advance", {}, voucher.arrears, voucher.arrears)
        )
    totals = defaultdict(lambda: ZERO)
    for _label, cells, _arr, _t in table.rows:
        for head_id, amount in cells.items():
            totals[head_id] += amount
    table.totals = dict(totals)
    table.total = voucher.payable
    table.discounts = sorted(discounts.items())
    return table


def guardian_phones(student_ids):
    return {
        link.student_id: link.guardian.phone
        for link in StudentGuardian.objects.filter(student_id__in=student_ids, is_primary_contact=True).select_related(
            "guardian"
        )
    }


def month_summary(branch, month):
    month = month_start(month)
    nxt = add_months(month, 1)
    billed = (
        Charge.objects.filter(branch=branch, month=month, is_cancelled=False).aggregate(t=Sum("amount"))["t"] or ZERO
    )
    payments = Payment.objects.filter(branch=branch, is_reversed=False, paid_on__gte=month, paid_on__lt=nxt)
    collected = payments.aggregate(t=Sum("amount"))["t"] or ZERO
    vouchers = Voucher.objects.filter(branch=branch, first_month__lte=month, last_month__gte=month).exclude(
        status=Voucher.Status.CANCELLED
    )
    status_counts = dict(vouchers.values_list("status").annotate(n=Count("id")))
    owed = outstanding(branch)
    return {
        "month": month,
        "billed": billed,
        "collected": collected,
        "vouchers": sum(status_counts.values()),
        "paid": status_counts.get(Voucher.Status.PAID, 0),
        "open": status_counts.get(Voucher.Status.OPEN, 0) + status_counts.get(Voucher.Status.SUPERSEDED, 0),
        "outstanding": sum((r["due"] for r in owed), ZERO),
        "defaulters": len(owed),
        "by_method": [
            {**row, "method": row["bank__name"] or Method(row["method"]).label}
            for row in payments.values("method", "bank__name")
            .annotate(total=Sum("amount"), n=Count("id"))
            .order_by("-total")
        ],
    }


def outstanding(branch, as_of=None, student_ids=None):
    """Per student with money owed: total due, oldest unpaid month, months of monthly fee unpaid.
    `as_of` limits to charges for months up to that date (e.g. only months already due)."""
    charges = (
        Charge.objects.filter(branch=branch, is_cancelled=False)
        .annotate(paid=Sum("allocations__amount"))
        .values("id", "student_id", "month", "amount", "paid", "head__kind")
    )
    if as_of:
        charges = charges.filter(month__lte=as_of)
    if student_ids is not None:
        charges = charges.filter(student_id__in=student_ids)
    per = defaultdict(lambda: {"due": ZERO, "oldest": None, "months": set()})
    for c in charges:
        left = c["amount"] - (c["paid"] or ZERO)
        if left <= 0:
            continue
        row = per[c["student_id"]]
        row["due"] += left
        row["oldest"] = min(row["oldest"] or c["month"], c["month"])
        if c["head__kind"] == FeeHead.Kind.MONTHLY:
            row["months"].add(c["month"])
    return [{"student_id": sid, **row, "months": len(row["months"])} for sid, row in per.items()]


def receiver_label(user):
    """ "Name (Designation)" of the person who received a payment: the staff record's designation,
    or their role when they have no staff record."""
    name = user.get_full_name() or user.username
    employee = getattr(user, "employee", None)
    if employee is not None and employee.designation:
        return f"{name} ({_(employee.designation)})"
    roles = [a.role.display_name for a in user.role_assignments.all() if a.is_active]
    return f"{name} ({roles[0]})" if roles else name


def collections(branch, date_from, date_to):
    payments = list(
        Payment.objects.filter(branch=branch, paid_on__gte=date_from, paid_on__lte=date_to)
        .select_related("student", "voucher", "bank", "received_by__employee")
        .prefetch_related("received_by__role_assignments__role")
        .order_by("paid_on", "pk")
    )
    labels = {}
    for p in payments:
        if p.received_by_id not in labels:
            labels[p.received_by_id] = receiver_label(p.received_by)
        p.receiver = labels[p.received_by_id]
    live = [p for p in payments if not p.is_reversed]
    by_method = defaultdict(lambda: ZERO)
    by_person = defaultdict(lambda: ZERO)
    cash_by_person = defaultdict(lambda: ZERO)
    by_bank = defaultdict(lambda: ZERO)
    for p in live:
        by_method[p.method_label] += p.amount
        by_person[p.receiver] += p.amount
        if p.method == Method.COUNTER:
            cash_by_person[p.receiver] += p.amount
        else:
            by_bank[p.method_label] += p.amount
    return {
        "payments": payments,
        "total": sum((p.amount for p in live), ZERO),
        "count": len(live),
        "cash_total": sum(cash_by_person.values(), ZERO),
        "bank_total": sum(by_bank.values(), ZERO),
        "by_method": sorted(by_method.items()),
        "by_person": sorted(by_person.items()),
        "cash_by_person": sorted(cash_by_person.items()),
        "by_bank": sorted(by_bank.items()),
    }


@dataclass
class RoyaltyRow:
    branch: object
    collected: Decimal
    billed: Decimal
    percent: Decimal

    @property
    def royalty(self):
        return (self.collected * self.percent / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def royalty(branches, month):
    """Royalty = the branch's percentage of all fees received during the month (D-040, confirmed
    16 Oct 2026). Fees billed for the month are shown alongside for comparison."""
    month = month_start(month)
    nxt = add_months(month, 1)
    ids = [b.id for b in branches]
    collected = dict(
        Payment.objects.filter(branch_id__in=ids, is_reversed=False, paid_on__gte=month, paid_on__lt=nxt)
        .values("branch_id")
        .annotate(t=Sum("amount"))
        .values_list("branch_id", "t")
    )
    billed = dict(
        Charge.objects.filter(branch_id__in=ids, month=month, is_cancelled=False)
        .values("branch_id")
        .annotate(t=Sum("amount"))
        .values_list("branch_id", "t")
    )
    return [
        RoyaltyRow(
            branch=b, collected=collected.get(b.id, ZERO), billed=billed.get(b.id, ZERO), percent=b.royalty_percent
        )
        for b in branches
    ]


def _royalty_of(collected, percent):
    return (collected * percent / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def royalty_balances(branches, until_month):
    """Per branch: royalty paid for `until_month` and the total still due for all months up to it
    (each month's royalty minus what was paid for it; what is left carries forward). Two grouped queries."""
    until = month_start(until_month)
    end = add_months(until, 1)
    ids = [b.id for b in branches]
    due = defaultdict(lambda: ZERO)
    percent = {b.id: b.royalty_percent for b in branches}
    received = (
        Payment.objects.filter(branch_id__in=ids, is_reversed=False, paid_on__lt=end)
        .annotate(m=TruncMonth("paid_on"))
        .values("branch_id", "m")
        .annotate(t=Sum("amount"))
    )
    for row in received:
        due[row["branch_id"]] += _royalty_of(row["t"], percent[row["branch_id"]])
    paid_total, paid_month = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for row in (
        RoyaltyPayment.objects.filter(branch_id__in=ids, month__lt=end)
        .values("branch_id", "month")
        .annotate(t=Sum("amount"))
    ):
        paid_total[row["branch_id"]] += row["t"]
        if row["month"] == until:
            paid_month[row["branch_id"]] += row["t"]
    return {b.id: {"paid": paid_month[b.id], "total_due": due[b.id] - paid_total[b.id]} for b in branches}


def royalty_ledger(branch, until_month, months=12):
    """The branch's royalty month by month: due, paid, left for that month, and the running total due
    (unpaid royalty from earlier months carries forward)."""
    until = month_start(until_month)
    start = add_months(until, -(months - 1))
    end = add_months(until, 1)
    collected = {
        row["m"]: row["t"]
        for row in Payment.objects.filter(branch=branch, is_reversed=False, paid_on__lt=end)
        .annotate(m=TruncMonth("paid_on"))
        .values("m")
        .annotate(t=Sum("amount"))
    }
    paid = dict(
        RoyaltyPayment.objects.filter(branch=branch, month__lt=end)
        .values("month")
        .annotate(t=Sum("amount"))
        .values_list("month", "t")
    )
    carried = sum((_royalty_of(t, branch.royalty_percent) for m, t in collected.items() if m < start), ZERO) - sum(
        (t for m, t in paid.items() if m < start), ZERO
    )
    rows, running, month = [], carried, start
    while month <= until:
        month_due = _royalty_of(collected.get(month, ZERO), branch.royalty_percent)
        month_paid = paid.get(month, ZERO)
        running += month_due - month_paid
        rows.append(
            {
                "month": month,
                "collected": collected.get(month, ZERO),
                "due": month_due,
                "paid": month_paid,
                "left": month_due - month_paid,
                "total_due": running,
            }
        )
        month = add_months(month, 1)
    while len(rows) > 1 and not (rows[0]["collected"] or rows[0]["paid"] or rows[0]["total_due"]):
        rows.pop(0)  # start at the first month with something to show
    return {"carried": carried, "rows": rows, "total_due": running}
