"""Stock and sales (M11). Stock in hand is the sum of an item's moves; nothing here edits a move.

A sale paid in cash or to a bank is also recorded as other income (head "Books and stationery sale" or "Uniform
sale"), so it shows in the cash & bank book and profit & loss. A sale added to the student's fee account becomes a
charge under "Others" and appears on the next fee voucher; it counts as income when the fee is paid."""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum

from apps.accounting.models import Income, IncomeHead
from apps.fees import services as fees
from apps.fees.models import FeeHead

from .models import Item, Sale, SaleLine, StockMove

ZERO = Decimal("0")
VIEW_PERM = "inventory.view_item"
SELL_PERM = "inventory.add_sale"
RECEIVE_PERM = "inventory.add_stockmove"
MANAGE_PERM = "inventory.change_item"
CANCEL_PERM = "inventory.change_sale"

INCOME_HEAD = {Item.Category.UNIFORM: "uniform", Item.Category.BOOKS: "books", Item.Category.STATIONERY: "books"}


class StockError(ValueError):
    pass


def on_hand(branch, items=None):
    """{item_id: quantity in stock} for the branch (items with no moves are left out)."""
    moves = StockMove.objects.filter(branch=branch)
    if items is not None:
        moves = moves.filter(item__in=items)
    return {r["item_id"]: r["q"] for r in moves.values("item_id").annotate(q=Sum("quantity"))}


def stock_rows(branch, include_inactive=False):
    """Every item with its stock, value at sale price and whether it needs reordering."""
    items = Item.objects.filter(branch=branch).select_related("class_level")
    if not include_inactive:
        items = items.filter(is_active=True)
    stock = on_hand(branch)
    rows = []
    for item in items:
        qty = stock.get(item.id, 0)
        rows.append(
            {
                "item": item,
                "qty": qty,
                "value": item.sale_price * max(qty, 0),
                "low": 0 < qty <= item.reorder_level,
                "out": qty <= 0,
            }
        )
    return rows


def move(item, kind, quantity, date, user, unit_cost=None, note=""):
    """Stock received (+), issued free (−) or a count correction (±). Sales use sell()."""
    if kind not in (StockMove.Kind.RECEIVED, StockMove.Kind.ISSUE, StockMove.Kind.CORRECTION):
        raise StockError("Use sell() for sales.")
    if quantity == 0:
        raise StockError("Quantity cannot be zero.")
    if kind == StockMove.Kind.RECEIVED and quantity < 0 or kind == StockMove.Kind.ISSUE and quantity > 0:
        quantity = -quantity
    with transaction.atomic():
        list(Item.objects.select_for_update().filter(pk=item.pk).order_by())
        if quantity < 0 and on_hand(item.branch, [item]).get(item.id, 0) + quantity < 0:
            raise StockError(item.name)
        m = StockMove.objects.create(
            branch_id=item.branch_id,
            item=item,
            date=date,
            kind=kind,
            quantity=quantity,
            unit_cost=unit_cost,
            note=note[:200],
            created_by=user,
        )
    return m


def _income_head(lines):
    """The income head for a sale: the one its items mostly belong to (by amount)."""
    by_head = defaultdict(lambda: ZERO)
    for item, _qty, amount in lines:
        by_head[INCOME_HEAD.get(item.category, "other")] += amount
    code = max(by_head, key=by_head.get)
    return IncomeHead.objects.filter(code=code).first() or IncomeHead.objects.get(code="other")


def _describe(lines):
    return ", ".join(f"{item.name} × {qty}" for item, qty, _a in lines)[:200]


def sell(branch, cart, date, paid_by, user, student=None, customer="", bank=None):
    """cart: [(item, quantity)]. Takes the items out of stock and records the money. Returns the Sale.

    Raises StockError naming an item that does not have enough stock."""
    cart = [(item, int(qty)) for item, qty in cart if int(qty) > 0]
    if not cart:
        raise StockError("Nothing to sell.")
    if any(item.branch_id != branch.id for item, _q in cart):
        raise StockError("Item belongs to another branch.")
    if paid_by == Sale.PaidBy.FEES and student is None:
        raise StockError("Choose the student.")
    if student is not None and student.branch_id != branch.id:
        raise StockError("Student belongs to another branch.")
    if paid_by == Sale.PaidBy.BANK and (bank is None or bank.branch_id != branch.id):
        raise StockError("Choose the bank.")
    with transaction.atomic():
        list(Item.objects.select_for_update().filter(pk__in=[i.pk for i, _q in cart]).order_by("pk").values("pk"))
        wanted = defaultdict(int)
        for item, qty in cart:
            wanted[item] += qty
        stock = on_hand(branch, list(wanted))
        for item, qty in wanted.items():
            if stock.get(item.id, 0) < qty:
                raise StockError(item.name)
        lines = [(item, qty, item.sale_price * qty) for item, qty in wanted.items()]
        total = sum((a for _i, _q, a in lines), ZERO)
        number = (Sale.objects.filter(branch=branch).aggregate(n=Max("number"))["n"] or 0) + 1
        buyer = student.full_name if student else customer.strip()
        sale = Sale.objects.create(
            branch=branch,
            number=number,
            date=date,
            student=student,
            customer=buyer[:120],
            paid_by=paid_by,
            bank=bank if paid_by == Sale.PaidBy.BANK else None,
            total=total,
            sold_by=user,
        )
        for item, qty, amount in lines:
            SaleLine.objects.create(
                branch=branch, sale=sale, item=item, quantity=qty, unit_price=item.sale_price, amount=amount
            )
            StockMove.objects.create(
                branch=branch, item=item, date=date, kind=StockMove.Kind.SALE, quantity=-qty, sale=sale,
                note=f"Sale {number}", created_by=user,
            )  # fmt: skip
        if total > 0:
            if paid_by == Sale.PaidBy.FEES:
                sale.charge = fees.add_charge(
                    student, FeeHead.objects.get(code="others"), date, total, user,
                    note=f"Sale {number}: {_describe(lines)}"[:200],
                )  # fmt: skip
            else:
                sale.income = Income.objects.create(
                    branch=branch,
                    date=date,
                    head=_income_head(lines),
                    amount=total,
                    description=f"Sale {number}: {_describe(lines)}"[:200],
                    received_from=buyer[:120],
                    received_in=Income.ReceivedIn.BANK if paid_by == Sale.PaidBy.BANK else Income.ReceivedIn.CASH,
                    bank=sale.bank,
                    reference=f"Sale {number}",
                    recorded_by=user,
                )
            sale.save(update_fields=["charge", "income"])
    return sale


def cancel_sale(sale, user, reason):
    """Puts the items back in stock and cancels the income or the fee charge. The sale is kept, marked cancelled."""
    reason = reason.strip()[:200]
    with transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale.pk)
        if sale.is_cancelled:
            return sale
        for line in sale.lines.select_related("item"):
            StockMove.objects.create(
                branch_id=sale.branch_id, item=line.item, date=sale.date, kind=StockMove.Kind.RETURN,
                quantity=line.quantity, sale=sale, note=f"Sale {sale.number} cancelled", created_by=user,
            )  # fmt: skip
        if sale.income_id and not sale.income.is_cancelled:
            income = sale.income
            income.is_cancelled, income.cancelled_by, income.cancel_reason = True, user, reason
            income.save()
        if sale.charge_id and not sale.charge.is_cancelled:
            fees.cancel_charge(sale.charge, user, reason)
        sale.is_cancelled, sale.cancel_reason = True, reason
        sale.save()
    return sale


def sales_by_item(branch, start, end):
    """[(item, quantity, amount)] sold between the dates (cancelled sales left out), largest amount first."""
    rows = (
        SaleLine.objects.filter(branch=branch, sale__is_cancelled=False, sale__date__gte=start, sale__date__lte=end)
        .values("item")
        .annotate(q=Sum("quantity"), a=Sum("amount"))
        .order_by("-a")
    )
    items = Item.objects.in_bulk([r["item"] for r in rows])
    return [(items[r["item"]], r["q"], r["a"]) for r in rows]
