"""Events & Tickets (project lead, 30 Oct 2026): events, ticket sales at the office with a printed receipt, refunds,
event expenses and each event's own profit or loss."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.functions import Length
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import ClassLevel, Section
from apps.core import escpos, exports
from apps.core.branch import current_branch
from apps.fees.models import BankAccount
from apps.organisation.models import AcademicSession, Campus
from apps.people.forms import section_order
from apps.people.models import Enrolment, Student
from apps.people.services import place_filter
from apps.people.services import search as search_students

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
    sales = event.sales.select_related("student", "class_level", "received_by", "refunded_by", "bank")
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
            "sales": sorted(sales, key=lambda x: (x.is_refunded, -x.number)),  # refunded ones at the end
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
    """Find students (same search as Students, plus class, section and campus) and sell tickets row by row; the
    list stays after each sale (project lead, 31 Oct 2026)."""
    branch = _branch(request, S.SELL_PERM)
    event = _event(branch, pk)
    if request.method == "POST":
        back = request.POST.get("next", "")
        back = back if back.startswith(f"/events/{event.pk}/sell/") else f"/events/{event.pk}/sell/"
        student = get_object_or_404(Student, pk=request.POST.get("student"), branch=branch)
        try:
            guests = max(int(request.POST.get("guests") or 0), 0)
        except ValueError:
            guests = 0
        paid_by = request.POST.get("paid_by", TicketSale.PaidBy.CASH)
        if paid_by not in TicketSale.PaidBy.values:
            paid_by = TicketSale.PaidBy.CASH
        bank = BankAccount.objects.filter(branch=branch, pk=request.POST.get("bank") or 0, is_active=True).first()
        try:
            sale = S.sell(
                event, student, guests, paid_by, request.POST.get("reference", "").strip(), request.user, bank
            )
        except S.SaleError as error:
            messages.error(request, f"{student.full_name}: {error}")
            return redirect(back)
        messages.success(
            request,
            _("%(s)s: %(n)s ticket(s), Rs %(a)s received by %(by)s.")
            % {"s": student.full_name, "n": sale.tickets, "a": f"{sale.amount:,.0f}", "by": _name(request.user)},
        )
        _print_receipt(request, sale)
        return redirect(back)
    session = AcademicSession.objects.filter(is_current=True).first()
    q = request.GET.get("q", "").strip()
    level_id, section_name, campus_id = (request.GET.get(k, "") for k in ("class", "section", "campus"))
    found = []
    searched = bool(q or level_id or section_name or campus_id)
    if searched:
        students = Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
        students = place_filter(search_students(students, q), session, level_id, section_name, campus_id)
        prices = {c.class_level_id: c.price for c in event.classes.all()}
        paid = set(event.sales.filter(is_refunded=False).values_list("student_id", flat=True))
        places = {
            e.student_id: e
            for e in Enrolment.objects.filter(session=session, student__in=students).select_related(
                "section__class_level", "section__campus"
            )
        } if session else {}  # fmt: skip
        for student in students.order_by(Length("admission_no"), "admission_no")[:300]:
            place = places.get(student.id)
            found.append(
                {
                    "student": student,
                    "place": place,
                    "has_ticket": student.id in paid,
                    "price": prices.get(place.section.class_level_id) if place else None,
                }  # fmt: skip
            )
        found.sort(key=lambda f: (f["place"].section.class_level.sort_order if f["place"] else 999,
                                  f["place"].section.name if f["place"] else "", f["student"].first_name))  # fmt: skip
    sections = Section.objects.filter(branch=branch, session=session) if session else Section.objects.none()
    return render(
        request,
        "events/sell.html",
        {
            "branch": branch,
            "event": event,
            "q": q,
            "filters": {"class": level_id, "section": section_name, "campus": campus_id},
            "levels": [c.class_level for c in event.classes.select_related("class_level")],
            "section_names": sorted(set(sections.values_list("name", flat=True)), key=section_order),
            "campuses": Campus.objects.filter(branch=branch, is_active=True),
            "searched": searched,
            "found": found,
            "paid_by": TicketSale.PaidBy.choices,
            "banks": BankAccount.objects.filter(branch=branch, is_active=True),
            "recent": event.sales.filter(received_by=request.user).select_related("student", "class_level")[:10],
            "here": request.get_full_path(),
        },
    )


@login_required
def report(request, pk):
    """The event report to print (A4): receipts sold, refunded receipts, expenses, money in by person and by bank;
    then a summary page with profit or loss (project lead, 31 Oct 2026)."""
    branch = _branch(request)
    event = _event(branch, pk)
    sales = event.sales.select_related("student", "class_level", "received_by", "refunded_by", "bank")
    sold = [s for s in sales.order_by("number") if not s.is_refunded]
    account = S.account(event)
    return render(
        request,
        "events/report.html",
        {
            "branch": branch,
            "event": event,
            "sold": sold,
            "refunded": [s for s in sales.order_by("number") if s.is_refunded],
            "expenses": event.expenses.filter(is_cancelled=False).select_related("recorded_by").order_by("date", "id"),
            "account": account,
            "classes": S.by_class(event),
            "receivers": S.by_receiver(event),
            "channels": S.by_channel(event),
            "sold_amount": sum((s.amount for s in sold), 0),
            "printed": timezone.localtime(),
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
