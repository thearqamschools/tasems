"""Finance → Shop & stock (M11): items, stock in and out, the sale counter with barcode, receipts and reports."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import exports
from apps.core.branch import current_branch
from apps.core.templatetags.tasems_tags import rupees
from apps.fees.models import BankAccount
from apps.people.models import Student

from . import services as S
from .forms import ItemForm, StockForm
from .models import Item, Sale, StockMove

CART_KEY = "inventory_cart"


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _can(request, branch, perm):
    return request.user.has_branch_perm(perm, branch.id)


@login_required
def index(request):
    branch = _branch(request)
    rows = S.stock_rows(branch, include_inactive=request.GET.get("show") == "all")
    category, q, status = request.GET.get("category", ""), request.GET.get("q", "").strip(), request.GET.get("status")
    shown = [
        r
        for r in rows
        if (not category or r["item"].category == category)
        and (not q or q.lower() in r["item"].name.lower() or q == r["item"].barcode)
        and (status != "low" or r["low"])
        and (status != "out" or r["out"])
    ]
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Stock in hand"),
            [_("Item"), _("Category"), _("Class"), _("Barcode"), _("Sale price (Rs)"), _("In stock"),
             _("Reorder level"), _("Value at sale price (Rs)")],
            ([r["item"].name, r["item"].get_category_display(), str(r["item"].class_level or ""), r["item"].barcode,
              r["item"].sale_price, r["qty"], r["item"].reorder_level, r["value"]] for r in shown),
            branch=branch,
        )  # fmt: skip
    live = [r for r in rows if r["item"].is_active]
    today = timezone.localdate()
    sold = Sale.objects.filter(branch=branch, is_cancelled=False, date__gte=today.replace(day=1), date__lte=today)
    return render(
        request,
        "inventory/index.html",
        {
            "branch": branch,
            "rows": shown,
            "categories": Item.Category.choices,
            "filters": {"category": category, "q": q, "status": status or "", "show": request.GET.get("show", "")},
            "kpi": {
                "items": len(live),
                "value": sum(r["value"] for r in live),
                "low": sum(1 for r in live if r["low"]),
                "out": sum(1 for r in live if r["out"]),
                "sold": sold.aggregate(t=Sum("total"))["t"] or 0,
            },
            "can_manage": _can(request, branch, S.MANAGE_PERM),
            "can_receive": _can(request, branch, S.RECEIVE_PERM),
            "can_sell": _can(request, branch, S.SELL_PERM),
        },
    )


@login_required
def item_form(request, pk=None):
    branch = _branch(request, S.MANAGE_PERM if pk else "inventory.add_item")
    item = get_object_or_404(Item, pk=pk, branch=branch) if pk else None
    form = ItemForm(request.POST or None, instance=item, branch=branch)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, _("%(name)s saved.") % {"name": item.name})
        return redirect("inventory:item", pk=item.pk)
    return render(request, "inventory/item_form.html", {"form": form, "item": item})


@login_required
def item(request, pk):
    branch = _branch(request)
    item = get_object_or_404(Item.objects.select_related("class_level"), pk=pk, branch=branch)
    moves = item.moves.select_related("created_by", "sale")
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Stock card") + f" — {item.name}",
            [_("Date"), _("What happened"), _("Quantity"), _("Purchase price (Rs)"), _("Note"), _("By")],
            ([m.date, m.get_kind_display(), m.quantity, m.unit_cost, m.note, m.created_by.get_username()]
             for m in moves),
            branch=branch,
        )  # fmt: skip
    page = exports.paginate(request, moves, 50)
    return render(
        request,
        "inventory/item.html",
        {
            "item": item,
            "page": page,
            "qty": S.on_hand(branch, [item]).get(item.id, 0),
            "can_manage": _can(request, branch, S.MANAGE_PERM),
            "can_receive": _can(request, branch, S.RECEIVE_PERM),
        },
    )


@login_required
def stock(request):
    branch = _branch(request, S.RECEIVE_PERM)
    initial = {"date": timezone.localdate(), "kind": StockMove.Kind.RECEIVED, "item": request.GET.get("item")}
    form = StockForm(request.POST or None, initial=initial, branch=branch)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            S.move(d["item"], d["kind"], d["quantity"], d["date"], request.user, d["unit_cost"], d["note"])
        except S.StockError:
            form.add_error(
                "quantity", _("Only %(n)s in stock.") % {"n": S.on_hand(branch, [d["item"]]).get(d["item"].id, 0)}
            )
        else:
            messages.success(request, _("Stock of %(name)s updated.") % {"name": d["item"].name})
            return redirect("inventory:item", pk=d["item"].pk)
    return render(request, "inventory/stock_form.html", {"form": form})


def _find_item(branch, code):
    """An item by its barcode, or by name when only one item matches."""
    code = code.strip()
    if not code:
        return None
    items = Item.objects.filter(branch=branch, is_active=True)
    exact = items.filter(barcode=code).first()
    if exact:
        return exact
    named = list(items.filter(name__icontains=code)[:2])
    return named[0] if len(named) == 1 else None


def _cart(request, branch):
    """[(item, quantity)] from the session, for this branch only."""
    raw = request.session.get(CART_KEY, {})
    if raw.get("branch") != branch.id:
        return []
    items = Item.objects.in_bulk([int(k) for k in raw.get("lines", {})])
    return [(items[int(k)], q) for k, q in raw.get("lines", {}).items() if int(k) in items]


def _save_cart(request, branch, lines):
    request.session[CART_KEY] = {"branch": branch.id, "lines": {str(i.id): q for i, q in lines if q > 0}}


@login_required
def sell(request):
    branch = _branch(request, S.SELL_PERM)
    lines = _cart(request, branch)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            item = _find_item(branch, request.POST.get("code", ""))
            try:
                qty = max(int(request.POST.get("qty") or 1), 1)
            except ValueError:
                qty = 1
            if item is None:
                messages.error(request, _("No item found for «%(c)s». Scan again or type more of the name.") % {
                    "c": request.POST.get("code", "")[:40]})  # fmt: skip
            else:
                merged = dict(lines)
                merged[item] = merged.get(item, 0) + qty
                _save_cart(request, branch, list(merged.items()))
            return redirect("inventory:sell")
        if action == "remove":
            _save_cart(request, branch, [(i, q) for i, q in lines if str(i.id) != request.POST.get("item")])
            return redirect("inventory:sell")
        if action == "clear":
            _save_cart(request, branch, [])
            return redirect("inventory:sell")
        if action == "complete":
            return _complete(request, branch, lines)
    stock = S.on_hand(branch, [i for i, _q in lines])
    cart = [
        {"item": i, "qty": q, "amount": i.sale_price * q, "short": stock.get(i.id, 0) < q, "stock": stock.get(i.id, 0)}
        for i, q in lines
    ]
    return render(
        request,
        "inventory/sell.html",
        {
            "branch": branch,
            "cart": cart,
            "total": sum(c["amount"] for c in cart),
            "items": Item.objects.filter(branch=branch, is_active=True).select_related("class_level"),
            "banks": BankAccount.objects.filter(branch=branch, is_active=True),
            "paid_by": Sale.PaidBy.choices,
            "post": request.POST,
        },
    )


def _complete(request, branch, lines):
    paid_by = request.POST.get("paid_by", Sale.PaidBy.CASH)
    adm = request.POST.get("admission_no", "").strip()
    student = Student.objects.filter(branch=branch, admission_no=adm).first() if adm else None
    bank = BankAccount.objects.filter(branch=branch, pk=request.POST.get("bank") or 0).first()
    error = None
    if not lines:
        error = _("Add at least one item.")
    elif adm and student is None:
        error = _("No student with admission no. %(n)s in this branch.") % {"n": adm}
    elif paid_by == Sale.PaidBy.FEES and student is None:
        error = _("Enter the student's admission no. to add the amount to their fee account.")
    elif paid_by == Sale.PaidBy.BANK and bank is None:
        error = _("Choose the bank the money came in.")
    if error is None:
        try:
            sale = S.sell(
                branch, lines, timezone.localdate(), paid_by, request.user,
                student=student, customer=request.POST.get("customer", ""), bank=bank,
            )  # fmt: skip
        except S.StockError as e:
            error = _("Not enough stock of %(name)s.") % {"name": e}
        else:
            _save_cart(request, branch, [])
            messages.success(request, _("Sale %(n)s saved: Rs %(t)s.") % {"n": sale.number, "t": rupees(sale.total)})
            return redirect("inventory:receipt", pk=sale.pk)
    messages.error(request, error)
    return redirect("inventory:sell")


@login_required
def receipt(request, pk):
    branch = _branch(request)
    sale = get_object_or_404(Sale.objects.select_related("student", "bank", "sold_by", "charge"), pk=pk, branch=branch)
    return render(
        request,
        "inventory/receipt.html",
        {
            "sale": sale,
            "branch": branch,
            "lines": sale.lines.select_related("item"),
            "can_cancel": _can(request, branch, S.CANCEL_PERM) and not sale.is_cancelled,
        },
    )


@login_required
@require_POST
def cancel(request, pk):
    branch = _branch(request, S.CANCEL_PERM)
    sale = Sale.objects.filter(pk=pk, branch=branch, is_cancelled=False).first()
    if sale is None:
        raise Http404
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, _("Give a reason for cancelling."))
    else:
        S.cancel_sale(sale, request.user, reason)
        messages.success(request, _("Sale cancelled. The items are back in stock and the money entry is cancelled."))
    return redirect("inventory:receipt", pk=sale.pk)


def _dates(request):
    today = timezone.localdate()

    def read(name, default):
        try:
            return dt.date.fromisoformat(request.GET.get(name, ""))
        except ValueError:
            return default

    start = read("from", today.replace(day=1))
    end = read("to", today)
    return (start, end) if start <= end else (end, start)


@login_required
def sales(request):
    branch = _branch(request)
    start, end = _dates(request)
    q = request.GET.get("q", "").strip()
    rows = Sale.objects.filter(branch=branch, date__gte=start, date__lte=end).select_related(
        "student", "sold_by", "bank"
    )
    if q:
        rows = rows.filter(
            Q(customer__icontains=q) | Q(student__admission_no=q) | Q(number=int(q) if q.isdigit() else 0)
        )
    live = rows.filter(is_cancelled=False)
    totals = {p: live.filter(paid_by=p).aggregate(t=Sum("total"))["t"] or 0 for p in Sale.PaidBy.values}
    if exports.wants_xlsx(request):
        if request.GET.get("by") == "item":
            return exports.xlsx_response(
                _("Sales by item") + f" {start:%d-%m-%Y} to {end:%d-%m-%Y}",
                [_("Item"), _("Category"), _("Quantity sold"), _("Amount (Rs)")],
                ([i.name, i.get_category_display(), qn, a] for i, qn, a in S.sales_by_item(branch, start, end)),
                branch=branch,
            )
        return exports.xlsx_response(
            _("Sales") + f" {start:%d-%m-%Y} to {end:%d-%m-%Y}",
            [_("Sale no."), _("Date"), _("Customer / student"), _("Admission no."), _("Paid by"), _("Sold by"),
             _("Status"), _("Amount (Rs)")],
            ([s.number, s.date, s.customer, s.student.admission_no if s.student else "", s.get_paid_by_display(),
              s.sold_by.get_username(), _("Cancelled") if s.is_cancelled else "", s.total] for s in rows),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "inventory/sales.html",
        {
            "branch": branch,
            "page": exports.paginate(request, rows, 50),
            "start": start,
            "end": end,
            "q": q,
            "totals": totals,
            "total": sum(totals.values()),
            "by_item": S.sales_by_item(branch, start, end),
            "can_sell": _can(request, branch, S.SELL_PERM),
        },
    )
