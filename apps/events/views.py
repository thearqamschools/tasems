"""Events & Tickets (project lead, 30 Oct 2026): events, ticket sales at the office with a printed receipt, refunds,
event expenses and each event's own profit or loss."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import ClassLevel
from apps.core import escpos, exports
from apps.core.branch import current_branch
from apps.people.models import Student

from . import services as S
from .forms import EventForm, ExpenseForm
from .models import Event, EventClass, EventExpense, TicketSale


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _can(request, branch):
    def has(perm):
        return request.user.has_branch_perm(perm, branch.id)

    return {
        "manage": has(S.MANAGE_PERM),
        "add": has("events.add_event"),
        "sell": has(S.SELL_PERM),
        "refund": has(S.REFUND_PERM),
        "expense": has(S.EXPENSE_PERM),
        "cancel_expense": has("events.change_eventexpense"),
    }


def _event(branch, pk):
    return get_object_or_404(Event, pk=pk, branch=branch)


def _name(user):
    return user.get_full_name() or user.username


@login_required
def index(request):
    branch = _branch(request)
    events = list(Event.objects.filter(branch=branch))
    for e in events:
        e.account = S.account(e)
    return render(request, "events/index.html", {"branch": branch, "events": events, "can": _can(request, branch)})


@login_required
def event_form(request, pk=None):
    branch = _branch(request, S.MANAGE_PERM if pk else "events.add_event")
    event = _event(branch, pk) if pk else None
    prices = {c.class_level_id: c.price for c in event.classes.all()} if event else {}
    form = EventForm(request.POST or None, instance=event, prices=prices)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.branch = branch
            if not event.pk:
                event.created_by = request.user
            event.save()
            chosen = form.prices()
            sold = set(event.sales.values_list("class_level_id", flat=True))
            for ec in event.classes.all():
                if ec.class_level not in chosen and ec.class_level_id not in sold:
                    ec.delete()  # a class with tickets sold stays in the event
            for level, price in chosen.items():
                EventClass.objects.update_or_create(
                    event=event, class_level=level, defaults={"price": price, "branch": branch}
                )
        messages.success(request, _("Event %(e)s saved.") % {"e": event.name})
        return redirect("events:detail", event.pk)
    return render(request, "events/form.html", {"branch": branch, "form": form, "event": event})


@login_required
def detail(request, pk):
    branch = _branch(request)
    event = _event(branch, pk)
    sales = event.sales.select_related("student", "class_level", "received_by", "refunded_by")
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            event.name,
            [_("Receipt no."), _("Date"), _("Admission no."), _("Student"), _("Class"), _("Section"),
             _("Extra tickets"), _("Amount (Rs)"), _("Paid by"), _("Received by"), _("Refunded")],
            ([s.receipt_no, timezone.localtime(s.received_at).strftime("%d/%m/%Y %H:%M"), s.student.admission_no,
              s.student.full_name, s.class_level.name, s.section_name, s.guest_tickets, s.amount,
              s.get_paid_by_display(), _name(s.received_by), _("Yes") if s.is_refunded else ""] for s in sales),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "events/detail.html",
        {
            "branch": branch,
            "event": event,
            "account": S.account(event),
            "classes": S.by_class(event),
            "receivers": S.by_receiver(event),
            "sales": sales,
            "expenses": event.expenses.select_related("recorded_by"),
            "can": _can(request, branch),
        },
    )


def _print_receipt(request, sale):
    """Sends the receipt to the branch's receipt printer; says what happened."""
    printer = sale.event.branch.receipt_printer
    if not printer:
        messages.warning(request, _("No receipt printer is set for this branch. Find it in Setup → Receipt printer."))
        return
    try:
        escpos.send(printer, escpos.ticket_receipt(sale, timezone.localtime()))
        messages.success(request, _("Receipt %(r)s printed.") % {"r": sale.receipt_no})
    except escpos.PrinterError as error:
        text = _("The receipt printer (%(p)s) did not answer: %(e)s. Check that it is on and connected.")
        messages.error(request, text % {"p": printer, "e": error})


@login_required
def sell(request, pk):
    branch = _branch(request, S.SELL_PERM)
    event = _event(branch, pk)
    if request.method == "POST":
        student = get_object_or_404(Student, pk=request.POST.get("student"), branch=branch)
        try:
            guests = max(int(request.POST.get("guests") or 0), 0)
        except ValueError:
            guests = 0
        paid_by = request.POST.get("paid_by", TicketSale.PaidBy.CASH)
        if paid_by not in TicketSale.PaidBy.values:
            paid_by = TicketSale.PaidBy.CASH
        try:
            sale = S.sell(event, student, guests, paid_by, request.POST.get("reference", "").strip(), request.user)
        except S.SaleError as error:
            messages.error(request, str(error))
            return redirect(f"{request.path}?q={student.admission_no}")
        messages.success(
            request,
            _("%(s)s: %(n)s ticket(s), Rs %(a)s received by %(by)s.")
            % {"s": student.full_name, "n": sale.tickets, "a": f"{sale.amount:,.0f}", "by": _name(request.user)},
        )
        _print_receipt(request, sale)
        return redirect("events:sell", event.pk)
    q = request.GET.get("q", "")
    found = []
    prices = {c.class_level_id: c.price for c in event.classes.all()}
    paid = set(event.sales.filter(is_refunded=False).values_list("student_id", flat=True))
    for student in S.student_search(branch, q):
        place = S.current_place(student)
        level_id = place.section.class_level_id if place else None
        found.append(
            {
                "student": student,
                "place": place,
                "price": prices.get(level_id),
                "has_ticket": student.id in paid,
            }
        )
    return render(
        request,
        "events/sell.html",
        {
            "branch": branch,
            "event": event,
            "q": q,
            "found": found,
            "paid_by": TicketSale.PaidBy.choices,
            "recent": event.sales.filter(received_by=request.user).select_related("student")[:10],
        },
    )


@login_required
def receipt(request, pk, sale_id):
    branch = _branch(request)
    event = _event(branch, pk)
    sale = get_object_or_404(TicketSale, pk=sale_id, event=event)
    if request.method == "POST":
        if not request.user.has_branch_perm(S.SELL_PERM, branch.id):
            raise PermissionDenied
        _print_receipt(request, sale)
        return redirect("events:receipt", event.pk, sale.pk)
    return render(request, "events/receipt.html", {"branch": branch, "event": event, "sale": sale})


@login_required
@require_POST
def refund(request, pk, sale_id):
    branch = _branch(request, S.REFUND_PERM)
    event = _event(branch, pk)
    sale = get_object_or_404(TicketSale, pk=sale_id, event=event)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, _("Give a reason for the refund."))
        return redirect("events:receipt", event.pk, sale.pk)
    try:
        S.refund(sale, request.user, reason)
        messages.success(
            request, _("Receipt %(r)s refunded: Rs %(a)s.") % {"r": sale.receipt_no, "a": f"{sale.amount:,.0f}"}
        )
    except S.SaleError as error:
        messages.error(request, str(error))
    return redirect("events:receipt", event.pk, sale.pk)


@login_required
def class_list(request, pk, level_id):
    branch = _branch(request)
    event = _event(branch, pk)
    level = get_object_or_404(ClassLevel, pk=level_id)
    rows = S.class_students(event, level)
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            f"{event.name} {level}",
            [_("Admission no."), _("Student"), _("Father name"), _("Section"), _("Ticket")],
            ([r["student"].admission_no, r["student"].full_name, r["student"].father_name, r["section"],
              _("Paid") if r["paid"] else _("Not yet")] for r in rows),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "events/class_list.html",
        {"branch": branch, "event": event, "level": level, "rows": rows, "paid": sum(1 for r in rows if r["paid"])},
    )


@login_required
def expense_new(request, pk):
    branch = _branch(request, S.EXPENSE_PERM)
    event = _event(branch, pk)
    form = ExpenseForm(request.POST or None, initial={"date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.branch, expense.event, expense.recorded_by = branch, event, request.user
        expense.save()
        messages.success(request, _("Expense of Rs %(a)s saved.") % {"a": f"{expense.amount:,.0f}"})
        return redirect("events:detail", event.pk)
    return render(request, "events/expense_form.html", {"branch": branch, "event": event, "form": form})


@login_required
@require_POST
def expense_cancel(request, pk, expense_id):
    branch = _branch(request, "events.change_eventexpense")
    event = _event(branch, pk)
    expense = get_object_or_404(EventExpense, pk=expense_id, event=event, is_cancelled=False)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, _("Give a reason for cancelling."))
    else:
        expense.is_cancelled, expense.cancel_reason = True, reason[:200]
        expense.save(update_fields=["is_cancelled", "cancel_reason"])
        messages.success(request, _("Expense cancelled."))
    return redirect("events:detail", event.pk)
