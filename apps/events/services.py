"""Selling tickets and keeping each event's own account (not linked to fees or the school's cash book)."""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.organisation.models import AcademicSession
from apps.people.models import Enrolment, Student

from .models import Event, EventExpense, TicketSale

VIEW_PERM = "events.view_event"
MANAGE_PERM = "events.change_event"  # make events, change prices, close sales
SELL_PERM = "events.add_ticketsale"  # take ticket money (those who receive fees)
REFUND_PERM = "events.refund_ticketsale"
EXPENSE_PERM = "events.add_eventexpense"


class SaleError(Exception):
    pass


def current_place(student):
    session = AcademicSession.objects.filter(is_current=True).first()
    if session is None:
        return None
    return Enrolment.objects.filter(student=student, session=session).select_related("section__class_level").first()


@transaction.atomic
def sell(event, student, guests, paid_by, reference, user):
    event = Event.objects.select_for_update().get(pk=event.pk)
    if not event.is_open:
        raise SaleError(_("Tickets for this event are closed."))
    if student.branch_id != event.branch_id or student.status != Student.Status.ACTIVE:
        raise SaleError(_("Tickets are sold only to current students of this branch."))
    place = current_place(student)
    prices = {c.class_level_id: c.price for c in event.classes.all()}
    if place is None or place.section.class_level_id not in prices:
        raise SaleError(_("%(s)s's class is not in this event.") % {"s": student.full_name})
    if guests and not event.guest_price:
        raise SaleError(_("This event has no extra tickets."))
    price = prices[place.section.class_level_id]
    number = (event.sales.aggregate(n=Max("number"))["n"] or 0) + 1
    return TicketSale.objects.create(
        branch_id=event.branch_id,
        event=event,
        number=number,
        student=student,
        class_level=place.section.class_level,
        section_name=place.section.name,
        student_price=price,
        guest_tickets=guests,
        guest_price=event.guest_price if guests else 0,
        amount=price + (event.guest_price * guests if guests else Decimal("0")),
        paid_by=paid_by,
        reference=reference[:60],
        received_by=user,
    )


@transaction.atomic
def refund(sale, user, reason):
    sale = TicketSale.objects.select_for_update().get(pk=sale.pk)
    if sale.is_refunded:
        raise SaleError(_("This receipt was already refunded."))
    sale.is_refunded, sale.refunded_by, sale.refunded_at, sale.refund_reason = True, user, timezone.now(), reason[:200]
    sale.save(update_fields=["is_refunded", "refunded_by", "refunded_at", "refund_reason"])
    return sale


def account(event):
    """The event's own account: tickets, money in, refunds, expenses, profit or loss."""
    sales = event.sales.all()
    paid = sales.filter(is_refunded=False)
    totals = paid.aggregate(students=Count("id"), guests=Sum("guest_tickets"), collected=Sum("amount"))
    refunded = sales.filter(is_refunded=True).aggregate(n=Count("id"), amount=Sum("amount"))
    spent = event.expenses.filter(is_cancelled=False).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    collected = totals["collected"] or Decimal("0")
    return {
        "students": totals["students"] or 0,
        "guests": totals["guests"] or 0,
        "collected": collected,
        "refunds": refunded["n"] or 0,
        "refunded": refunded["amount"] or Decimal("0"),
        "expenses": spent,
        "result": collected - spent,
    }


def by_class(event):
    """Each class in the event: price, students in it now, tickets paid, money in."""
    session = AcademicSession.objects.filter(is_current=True).first()
    paid = {
        r["class_level"]: r
        for r in event.sales.filter(is_refunded=False)
        .values("class_level")
        .annotate(n=Count("student", distinct=True), guests=Sum("guest_tickets"), amount=Sum("amount"))
    }
    rows = []
    for ec in event.classes.select_related("class_level"):
        enrolled = 0
        if session:
            enrolled = Enrolment.objects.filter(
                session=session,
                section__branch_id=event.branch_id,
                section__class_level=ec.class_level,
                student__status=Student.Status.ACTIVE,
            ).count()
        p = paid.get(ec.class_level_id, {})
        rows.append(
            {
                "level": ec.class_level,
                "price": ec.price,
                "enrolled": enrolled,
                "paid": p.get("n", 0),
                "guests": p.get("guests") or 0,
                "amount": p.get("amount") or Decimal("0"),
            }
        )
    return rows


def class_students(event, level):
    """Students of one class with whether they have a ticket (for the class teacher's list)."""
    session = AcademicSession.objects.filter(is_current=True).first()
    if session is None:
        return []
    paid = set(event.sales.filter(is_refunded=False).values_list("student_id", flat=True))
    places = (
        Enrolment.objects.filter(
            session=session, section__branch_id=event.branch_id, section__class_level=level,
            student__status=Student.Status.ACTIVE,
        )
        .select_related("student", "section")
        .order_by("section__name", "student__first_name")
    )  # fmt: skip
    return [{"student": e.student, "section": e.section.name, "paid": e.student_id in paid} for e in places]


def by_receiver(event):
    """Who received how much (to hand the cash over)."""
    out = defaultdict(lambda: {"n": 0, "amount": Decimal("0")})
    for s in event.sales.filter(is_refunded=False).select_related("received_by"):
        key = s.received_by.get_full_name() or s.received_by.username
        out[key]["n"] += 1
        out[key]["amount"] += s.amount
    return sorted(out.items())


def student_search(branch, q):
    q = q.strip()
    if not q:
        return Student.objects.none()
    match = Q(admission_no__startswith=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
    match |= Q(father_name__icontains=q)
    return Student.objects.filter(branch=branch, status=Student.Status.ACTIVE).filter(match)[:20]


def expense_total(event):
    return EventExpense.objects.filter(event=event, is_cancelled=False).aggregate(t=Sum("amount"))["t"] or 0
