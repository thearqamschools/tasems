"""Fee rules (confirmed by the project lead, 16 Oct 2026 — DECISIONS D-033 to D-036):

* Monthly fee every month; annual charges once a year (April); summer vacation work in July
  when an amount is set; admission, re-admission and registration chosen on a voucher.
* Sibling fee: children with the same father's CNIC in the same branch — the first child
  (earliest admitted) pays the full monthly fee, every brother or sister pays the sibling amount.
* Special discounts apply only after the principal or a director approves them; a student gets
  either the sibling discount or the special discount on a head, whichever is larger.
* Due date: the branch's due day (10th). Vouchers made after that day are due the day they are made;
  the person generating can choose another date.
* Unpaid balance moves to the next voucher, and every voucher not paid in full by its due date
  adds the late fine (Rs 200) once.
"""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import AuditEvent
from apps.people.models import Enrolment, Student

from .models import (
    BranchFeeSettings,
    Charge,
    Concession,
    FeeHead,
    FeeRate,
    Payment,
    PaymentAllocation,
    Voucher,
    VoucherCounter,
    month_start,
    months_between,
)

ZERO = Decimal("0")
VIEW_PERM = "fees.view_voucher"
VOUCHER_PERM = "fees.add_voucher"
PAY_PERM = "fees.add_payment"
REVERSE_PERM = "fees.change_payment"
CANCEL_PERM = "fees.change_voucher"
CHARGE_PERM = "fees.add_charge"
CANCEL_CHARGE_PERM = "fees.change_charge"
CONCESSION_PERM = "fees.add_concession"
APPROVE_PERM = "fees.approve_concession"
ROYALTY_PERM = "fees.view_royalty"
ROYALTY_RECORD_PERM = "fees.add_royaltypayment"


def default_due_date(branch, first_month, today=None):
    """The due day of the billing month; if that has already passed, today."""
    today = today or timezone.localdate()
    fee_settings = BranchFeeSettings.for_branch(branch)
    due = dt.date(first_month.year, first_month.month, fee_settings.due_day)
    return max(due, today)


# --- Amounts ---------------------------------------------------------------------------------


class RateBook:
    """All of a branch's fee amounts, loaded once."""

    def __init__(self, branch):
        self.rates = defaultdict(list)
        for rate in FeeRate.objects.filter(branch=branch).select_related("head"):
            self.rates[rate.head_id].append(rate)

    def rate(self, head, class_level_id, month):
        best = None
        for r in self.rates.get(head.id, []):
            if r.effective_from > month:
                continue
            if r.class_level_id not in (None, class_level_id):
                continue
            key = (r.class_level_id is not None, r.effective_from)
            if best is None or key > best[0]:
                best = (key, r)
        return best[1] if best else None


def first_children(branch):
    """father's CNIC → id of the child who pays the full fee (earliest admitted active child)."""
    first = {}
    for sid, cnic in (
        Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
        .exclude(father_cnic="")
        .order_by("admission_date", "pk")
        .values_list("id", "father_cnic")
    ):
        first.setdefault(cnic, sid)
    return first


def is_sibling(student, firsts):
    return bool(student.father_cnic) and firsts.get(student.father_cnic, student.id) != student.id


def approved_concessions(student_ids):
    out = defaultdict(list)
    for c in Concession.objects.filter(student_id__in=student_ids, status=Concession.Status.APPROVED):
        out[c.student_id].append(c)
    return out


def price(head, rate, month, sibling, concessions):
    """(gross, discount, reason) for one head and month, or None if nothing is charged."""
    if rate is None or rate.amount <= 0:
        return None
    gross, discount, reason = rate.amount, ZERO, ""
    # An agreed fee (e.g. carried over from the previous software) replaces every other rule.
    agreed = next((c for c in concessions if c.head_id == head.id and c.kind == "fixed" and c.covers(month)), None)
    if agreed is not None:
        return gross, agreed.discount_on(gross), "Agreed fee"
    if sibling and rate.sibling_amount is not None and rate.sibling_amount < gross:
        discount, reason = gross - rate.sibling_amount, "Sibling"
    for c in concessions:
        if c.head_id == head.id and c.covers(month):
            off = c.discount_on(gross)
            if off > discount:
                discount, reason = off, f"Special discount: {c.reason}"[:120]
    return gross, discount, reason


def automatic_heads(month, heads):
    for head in heads:
        if head.kind == FeeHead.Kind.MONTHLY:
            yield head
        elif head.kind in (FeeHead.Kind.YEARLY, FeeHead.Kind.SEASONAL) and month.month in (head.charge_months or []):
            yield head


# --- Balances and allocation -----------------------------------------------------------------


def live_charges(student):
    return Charge.objects.filter(student=student, is_cancelled=False)


def live_payments(student):
    return Payment.objects.filter(student=student, is_reversed=False)


def balance(student):
    charged = live_charges(student).aggregate(t=Sum("amount"))["t"] or ZERO
    paid = live_payments(student).aggregate(t=Sum("amount"))["t"] or ZERO
    return charged - paid


def reallocate(student):
    """Matches payments to the oldest charges first. Safe to run any time."""
    PaymentAllocation.objects.filter(payment__student=student).delete()
    charges = list(live_charges(student).select_related("head").order_by("month", "head__sort_order", "pk"))
    payments = list(live_payments(student).order_by("paid_on", "pk"))
    rows, ci, left_on_charge = [], 0, None
    for p in payments:
        left = p.amount
        while left > 0 and ci < len(charges):
            charge = charges[ci]
            if left_on_charge is None:
                left_on_charge = charge.amount
            take = min(left, left_on_charge)
            if take > 0:
                rows.append(PaymentAllocation(branch_id=student.branch_id, payment=p, charge=charge, amount=take))
            left -= take
            left_on_charge -= take
            if left_on_charge <= 0:
                ci, left_on_charge = ci + 1, None
    PaymentAllocation.objects.bulk_create(rows)


def unpaid_charges(student):
    """Charges not yet fully paid, oldest first, with what is left on each."""
    out = []
    for c in live_charges(student).select_related("head").annotate(paid=Sum("allocations__amount")):
        left = c.amount - (c.paid or ZERO)
        if left > 0:
            out.append((c, left))
    out.sort(key=lambda x: (x[0].month, x[0].head.sort_order, x[0].pk))
    return out


def refresh_status(student):
    """The newest open voucher becomes Paid once nothing is owed; a reversal can reopen it."""
    owed = balance(student)
    latest = Voucher.objects.filter(student=student).exclude(status=Voucher.Status.CANCELLED).order_by("-pk").first()
    if latest is None:
        return
    if owed <= 0 and latest.status == Voucher.Status.OPEN:
        latest.status = Voucher.Status.PAID
        latest.save(update_fields=["status", "updated_at"])
    elif owed > 0 and latest.status == Voucher.Status.PAID:
        latest.status = Voucher.Status.OPEN
        latest.save(update_fields=["status", "updated_at"])


# --- Late fines ------------------------------------------------------------------------------


def _was_late(voucher):
    """True if what this voucher asked for was not fully paid by its due date. What it asked for
    is everything billed on it and on the student's earlier vouchers."""
    if voucher.payable <= 0:
        return False
    charged = (
        Charge.objects.filter(student_id=voucher.student_id, is_cancelled=False, voucher_id__lte=voucher.pk).aggregate(
            t=Sum("amount")
        )["t"]
        or ZERO
    )
    paid = (
        Payment.objects.filter(student_id=voucher.student_id, is_reversed=False, paid_on__lte=voucher.due_on).aggregate(
            t=Sum("amount")
        )["t"]
        or ZERO
    )
    return charged - paid > 0


def pending_fines(student, as_of):
    """Vouchers due before `as_of`, not paid in full by their due date and not yet fined."""
    candidates = Voucher.objects.filter(
        student=student, due_on__lt=as_of, late_fine__gt=0, fine_charge__isnull=True
    ).exclude(status=Voucher.Status.CANCELLED)
    return [v for v in candidates.order_by("pk") if _was_late(v)]


def apply_late_fines(student, as_of, user):
    """Adds the late fine once for each voucher in `pending_fines`. Returns how many were added."""
    late = pending_fines(student, as_of)
    if not late:
        return 0
    fine_head = FeeHead.objects.get(code="fine")
    for v in late:
        Charge.objects.create(
            branch_id=student.branch_id,
            student=student,
            head=fine_head,
            month=v.last_month,
            gross=v.late_fine,
            amount=v.late_fine,
            source=Charge.Source.FINE,
            fine_for=v,
            note=f"Late payment of voucher {v.number}",
            created_by=user,
        )
    return len(late)


# --- Vouchers --------------------------------------------------------------------------------


def reserve_numbers(count):
    counter = VoucherCounter.objects.select_for_update().order_by("pk").first()
    if counter is None:
        counter = VoucherCounter.objects.create()
        counter = VoucherCounter.objects.select_for_update().get(pk=counter.pk)
    first = counter.next_number
    counter.next_number = first + count
    counter.save()
    return iter(range(first, first + count))


def enrolled_students(branch, session, section_ids=None):
    """Active students placed in a section this session, with their section."""
    qs = Enrolment.objects.filter(branch=branch, session=session, student__status=Student.Status.ACTIVE).select_related(
        "student", "section", "section__class_level"
    )
    if section_ids:
        qs = qs.filter(section_id__in=section_ids)
    return qs.order_by("section__class_level__sort_order", "section__name", "roll_no", "student__first_name")


def _issue(student, section, months, due_on, user, numbers, book, heads, firsts, concessions, extras, fee_settings):
    """Creates one voucher. `extras` = [(head, gross, discount, reason, month, note)] chosen by staff."""
    today = timezone.localdate()
    apply_late_fines(student, today, user)

    new = []
    level_id = section.class_level_id if section else None
    sibling = is_sibling(student, firsts)
    existing = set(
        live_charges(student).filter(source=Charge.Source.AUTO, month__in=months).values_list("head_id", "month")
    )
    for month in months:
        for head in automatic_heads(month, heads):
            if (head.id, month) in existing:
                continue
            priced = price(head, book.rate(head, level_id, month), month, sibling, concessions)
            if priced:
                gross, discount, reason = priced
                new.append((head, month, gross, discount, reason, Charge.Source.AUTO, ""))
    for head, gross, discount, reason, month, note in extras:
        new.append((head, month, gross, discount, reason, Charge.Source.MANUAL, note))

    voucher = Voucher.objects.create(
        branch_id=student.branch_id,
        number=next(numbers),
        student=student,
        section=section,
        first_month=months[0],
        last_month=months[-1],
        issued_on=today,
        due_on=due_on,
        late_fine=fee_settings.late_fine,
        created_by=user,
    )
    Charge.objects.bulk_create(
        [
            Charge(
                branch_id=student.branch_id,
                student=student,
                head=head,
                month=month,
                gross=gross,
                discount=discount,
                amount=gross - discount,
                discount_reason=reason,
                source=source,
                note=note,
                voucher=voucher,
                created_by=user,
            )
            for head, month, gross, discount, reason, source, note in new
        ]
    )
    # Charges added since the last voucher (fines, hand-added items) are billed now as well.
    live_charges(student).filter(voucher__isnull=True).update(voucher=voucher)

    current = live_charges(student).filter(voucher=voucher).aggregate(t=Sum("amount"))["t"] or ZERO
    total = balance(student)
    voucher.current = current
    voucher.arrears = total - current
    voucher.payable = max(total, ZERO)
    voucher.status = Voucher.Status.OPEN if total > 0 else Voucher.Status.PAID
    voucher.save()
    Voucher.objects.filter(student=student, status=Voucher.Status.OPEN).exclude(pk=voucher.pk).update(
        status=Voucher.Status.SUPERSEDED
    )
    reallocate(student)
    return voucher


def covered(student_ids, months):
    """Students who already have a voucher for any of these months."""
    q = Q()
    for m in months:
        q |= Q(first_month__lte=m, last_month__gte=m)
    return set(
        Voucher.objects.filter(student_id__in=student_ids)
        .exclude(status=Voucher.Status.CANCELLED)
        .filter(q)
        .values_list("student_id", flat=True)
    )


@transaction.atomic
def generate_vouchers(branch, session, first_month, last_month, due_on, user, section_ids=None):
    """Monthly vouchers for every active student of the branch (or of the chosen sections).
    Students who already have a voucher for one of these months are skipped."""
    months = months_between(first_month, last_month)
    enrolments = list(enrolled_students(branch, session, section_ids))
    done = covered([e.student_id for e in enrolments], months)
    todo = [e for e in enrolments if e.student_id not in done]
    numbers = reserve_numbers(len(todo))
    book, heads, firsts = RateBook(branch), list(FeeHead.objects.filter(is_active=True)), first_children(branch)
    concessions = approved_concessions([e.student_id for e in todo])
    fee_settings = BranchFeeSettings.for_branch(branch)
    vouchers = [
        _issue(
            e.student,
            e.section,
            months,
            due_on,
            user,
            numbers,
            book,
            heads,
            firsts,
            concessions[e.student_id],
            [],
            fee_settings,
        )
        for e in todo
    ]
    if vouchers:
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.CREATE,
            model_label="fees.Voucher",
            object_id=f"batch:{first_month:%Y-%m}",
            object_repr=f"{len(vouchers)} vouchers {first_month:%b %Y}–{last_month:%b %Y}",
            branch_id=branch.id,
            changes={
                "numbers": f"{vouchers[0].number}–{vouchers[-1].number}",
                "due_on": str(due_on),
                "sections": section_ids or "all",
            },
        )
    return {"created": vouchers, "skipped": len(done)}


@transaction.atomic
def issue_voucher(student, session, first_month, last_month, due_on, user, extras=()):
    """One student's voucher, e.g. at admission or for several months paid together."""
    enrolment = Enrolment.objects.filter(student=student, session=session).select_related("section").first()
    section = enrolment.section if enrolment else None
    branch = student.branch
    voucher = _issue(
        student,
        section,
        months_between(first_month, last_month),
        due_on,
        user,
        reserve_numbers(1),
        RateBook(branch),
        list(FeeHead.objects.filter(is_active=True)),
        first_children(branch),
        approved_concessions([student.id])[student.id],
        list(extras),
        BranchFeeSettings.for_branch(branch),
    )
    return voucher


def one_time_price(student, head, class_level_id, month):
    """Suggested amount for a head chosen by hand (admission, registration, annual …)."""
    rate = RateBook(student.branch).rate(head, class_level_id, month)
    return rate.amount if rate else ZERO


@transaction.atomic
def cancel_voucher(voucher, user, reason):
    if voucher.payments.filter(is_reversed=False).exists():
        raise ValueError(_("A voucher with payments cannot be cancelled; reverse the payments first."))
    if voucher.status == Voucher.Status.CANCELLED:
        return
    later = Voucher.objects.filter(student=voucher.student, pk__gt=voucher.pk).exclude(status=Voucher.Status.CANCELLED)
    if later.exists():
        raise ValueError(_("Only the student's newest voucher can be cancelled."))
    voucher.charges.filter(is_cancelled=False).exclude(source=Charge.Source.FINE).update(
        is_cancelled=True, cancelled_by=user, cancel_reason=f"Voucher {voucher.number} cancelled: {reason}"[:200]
    )
    # Fines and charges from earlier months go back to being unbilled, for the next voucher.
    voucher.charges.filter(is_cancelled=False).update(voucher=None)
    voucher.status, voucher.cancel_reason = Voucher.Status.CANCELLED, reason[:200]
    voucher.save()
    previous = Voucher.objects.filter(student=voucher.student, status=Voucher.Status.SUPERSEDED).order_by("-pk").first()
    if previous:
        previous.status = Voucher.Status.OPEN
        previous.save(update_fields=["status", "updated_at"])
    reallocate(voucher.student)
    refresh_status(voucher.student)
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.UPDATE,
        model_label="fees.Voucher",
        object_id=str(voucher.pk),
        object_repr=str(voucher)[:255],
        branch_id=voucher.branch_id,
        changes={"status": {"from": "open", "to": "cancelled"}, "reason": reason},
    )


@transaction.atomic
def add_charge(student, head, month, gross, user, note="", discount=ZERO, reason=""):
    """A hand-added charge (e.g. Others, Gen. Exp.). It appears on the next voucher."""
    charge = Charge.objects.create(
        branch_id=student.branch_id,
        student=student,
        head=head,
        month=month_start(month),
        gross=gross,
        discount=discount,
        amount=gross - discount,
        discount_reason=reason,
        source=Charge.Source.MANUAL,
        note=note,
        created_by=user,
    )
    reallocate(student)
    refresh_status(student)
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.CREATE,
        model_label="fees.Charge",
        object_id=str(charge.pk),
        object_repr=f"{student} — {charge}"[:255],
        branch_id=student.branch_id,
        changes={"amount": str(charge.amount), "note": note},
    )
    return charge


@transaction.atomic
def cancel_charge(charge, user, reason):
    charge.is_cancelled, charge.cancelled_by, charge.cancel_reason = True, user, reason[:200]
    charge.save()
    reallocate(charge.student)
    refresh_status(charge.student)
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.UPDATE,
        model_label="fees.Charge",
        object_id=str(charge.pk),
        object_repr=f"{charge.student} — {charge}"[:255],
        branch_id=charge.branch_id,
        changes={"is_cancelled": {"from": False, "to": True}, "reason": reason},
    )


# --- Payments --------------------------------------------------------------------------------


def amount_due_now(voucher, on_date=None):
    """What the parent should pay today against this voucher: the student's whole balance,
    plus the voucher's late fine if it is past due and not yet added."""
    on_date = on_date or timezone.localdate()
    fine = sum((v.late_fine for v in pending_fines(voucher.student, on_date)), ZERO)
    return max(balance(voucher.student) + fine, ZERO), fine


@transaction.atomic
def record_payment(
    student, amount, paid_on, method, user, voucher=None, reference="", note="", bank=None, attachment=None
):
    if voucher is not None and voucher.student_id != student.id:
        raise ValueError("Voucher belongs to another student.")
    if bank is not None and bank.branch_id != student.branch_id:
        raise ValueError("Bank belongs to another branch.")
    payment = Payment(
        branch_id=student.branch_id,
        student=student,
        voucher=voucher,
        amount=amount,
        paid_on=paid_on,
        method=method,
        bank=bank,
        reference=reference,
        note=note,
        received_by=user,
    )
    if attachment:
        payment.attachment = attachment
    payment.save()
    # A late payment brings its fine with it (one fine per voucher).
    apply_late_fines(student, paid_on, user)
    reallocate(student)
    refresh_status(student)
    return payment


@transaction.atomic
def reverse_payment(payment, user, reason):
    if payment.is_reversed:
        return
    payment.is_reversed = True
    payment.reversed_by = user
    payment.reversed_at = timezone.now()
    payment.reverse_reason = reason[:200]
    payment.save()
    reallocate(payment.student)
    refresh_status(payment.student)


# --- Special discounts -----------------------------------------------------------------------


@transaction.atomic
def set_agreed_fee(student, amount, user, session=None):
    """Records a student's agreed monthly fee (e.g. from the previous software) as an approved
    'agreed fee' on the monthly fee head. It replaces the sibling rule for this student."""
    tuition = FeeHead.objects.get(code="tuition")
    start = session.starts_on if session else month_start(timezone.localdate())
    Concession.objects.filter(student=student, head=tuition, kind="fixed", status=Concession.Status.APPROVED).update(
        status=Concession.Status.ENDED
    )
    return Concession.objects.create(
        branch_id=student.branch_id,
        student=student,
        head=tuition,
        kind="fixed",
        value=amount,
        starts_on=start,
        reason="Monthly fee from the previous software",
        status=Concession.Status.APPROVED,
        requested_by=user,
        decided_by=user,
        decided_at=timezone.now(),
    )


@transaction.atomic
def discount_at_admission(student, discount_type, user):
    """The discount chosen on the admission form, on the monthly fee from the admission month.
    It applies at once unless head office marked that discount as needing approval."""
    approved = not discount_type.needs_approval
    return Concession.objects.create(
        branch_id=student.branch_id,
        student=student,
        head=FeeHead.objects.get(code="tuition"),
        kind=Concession.Kind.PERCENT,
        value=discount_type.percent,
        starts_on=month_start(student.admission_date),
        reason=discount_type.name,
        discount_type=discount_type,
        status=Concession.Status.APPROVED if approved else Concession.Status.PENDING,
        requested_by=user,
        decided_by=user if approved else None,
        decided_at=timezone.now() if approved else None,
    )


def decide_concession(concession, user, approve):
    concession.status = Concession.Status.APPROVED if approve else Concession.Status.REJECTED
    concession.decided_by = user
    concession.decided_at = timezone.now()
    concession.save()
