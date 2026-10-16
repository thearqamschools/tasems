import datetime as dt
from collections import Counter
from urllib.parse import quote

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.people.models import Student

from .models import FollowUp, Inquiry, Source

VIEW_PERM = "admissions.view_inquiry"
ADD_PERM = "admissions.add_inquiry"
CHANGE_PERM = "admissions.change_inquiry"


def matches(branch, phone, exclude=None):
    """Earlier inquiries and children already at school with the same mobile number."""
    inquiries = Inquiry.objects.filter(branch=branch, phone=phone).select_related("class_level")
    if exclude is not None:
        inquiries = inquiries.exclude(pk=exclude.pk)
    students = (
        Student.objects.filter(branch=branch, guardian_links__guardian__phone=phone, status=Student.Status.ACTIVE)
        .distinct()
        .order_by("first_name")
    )
    return list(inquiries[:10]), list(students[:10])


@transaction.atomic
def create(inquiry, user):
    inquiry.created_by = user
    if inquiry.assigned_to_id is None:
        inquiry.assigned_to = user
    if inquiry.next_follow_up is None:
        inquiry.next_follow_up = timezone.localdate() + dt.timedelta(days=1)
    inquiry.save()
    FollowUp.objects.create(
        branch_id=inquiry.branch_id,
        inquiry=inquiry,
        kind=FollowUp.Kind.NOTE,
        note=f"Inquiry received ({inquiry.get_source_display()})." + (f" {inquiry.notes}" if inquiry.notes else ""),
        at=timezone.now(),
        by=user,
    )
    return inquiry


@transaction.atomic
def record(inquiry, user, kind, note="", next_follow_up=None, status=None, lost_reason="", visit_at=None):
    """Adds a follow-up and, if given, moves the inquiry to a new status."""
    FollowUp.objects.create(
        branch_id=inquiry.branch_id, inquiry=inquiry, kind=kind, note=note, at=timezone.now(), by=user
    )
    fields = ["next_follow_up", "updated_at"]
    inquiry.next_follow_up = next_follow_up
    if visit_at is not None:
        inquiry.visit_at = visit_at
        fields.append("visit_at")
    if status and status != inquiry.status:
        before = inquiry.get_status_display()
        inquiry.status = status
        inquiry.lost_reason = lost_reason if status == Inquiry.Status.LOST else ""
        inquiry.closed_on = timezone.localdate() if status in (Inquiry.Status.ADMITTED, Inquiry.Status.LOST) else None
        if not inquiry.is_open:
            inquiry.next_follow_up = None
        fields += ["status", "lost_reason", "closed_on"]
        reason = f" — {inquiry.get_lost_reason_display()}" if inquiry.lost_reason else ""
        FollowUp.objects.create(
            branch_id=inquiry.branch_id,
            inquiry=inquiry,
            kind=FollowUp.Kind.STATUS,
            note=f"{before} → {inquiry.get_status_display()}{reason}",
            at=timezone.now(),
            by=user,
        )
    inquiry.save(update_fields=fields)
    return inquiry


@transaction.atomic
def admit(inquiry, student, user):
    inquiry.student = student
    inquiry.save(update_fields=["student", "updated_at"])
    record(
        inquiry,
        user,
        FollowUp.Kind.NOTE,
        f"Student record made: {student.admission_no}",
        status=Inquiry.Status.ADMITTED,
    )


def whatsapp_link(phone, message=""):
    """Opens WhatsApp on the phone or computer with the parent's chat and a ready message.
    No WhatsApp API is needed; the staff member presses Send themselves."""
    number = "92" + phone[1:] if phone.startswith("0") else phone
    return f"https://wa.me/{number}" + (f"?text={quote(message)}" if message else "")


def default_message(inquiry, branch):
    return (
        f"Assalamualaikum {inquiry.parent_name}, thank you for your interest in The Arqam Schools "
        f"({branch.name}) for {inquiry.child_name} ({inquiry.class_level.name}). "
        "We would be happy to welcome you for a campus visit. "
        "For any question: 041-2660265, WhatsApp 0339-2406479."
    )


def due(branch, user=None, day=None):
    day = day or timezone.localdate()
    qs = Inquiry.objects.filter(branch=branch, status__in=Inquiry.OPEN, next_follow_up__lte=day)
    if user is not None:
        qs = qs.filter(assigned_to=user)
    return qs.select_related("class_level", "assigned_to").order_by("next_follow_up", "created_at")


def report(branch, start, end):
    """Inquiries received between two dates: by source, class and status, with how many joined."""
    qs = Inquiry.objects.filter(branch=branch, created_at__date__gte=start, created_at__date__lte=end)
    total = qs.count()
    admitted = qs.filter(status=Inquiry.Status.ADMITTED).count()
    labels = dict(Source.choices)
    by_source = [
        (labels.get(r["source"], r["source"]), r["n"], r["won"])
        for r in qs.values("source")
        .annotate(n=Count("id"), won=Count("id", filter=Q(status="admitted")))
        .order_by("-n")
    ]
    by_class = [
        (r["class_level__name"], r["n"], r["won"])
        for r in qs.values("class_level__name", "class_level__sort_order")
        .annotate(n=Count("id"), won=Count("id", filter=Q(status="admitted")))
        .order_by("class_level__sort_order")
    ]
    statuses = Counter(dict(qs.values_list("status").annotate(n=Count("id"))))
    lost = Counter(dict(qs.filter(status="lost").values_list("lost_reason").annotate(n=Count("id"))))
    return {
        "total": total,
        "admitted": admitted,
        "rate": round(admitted * 100 / total) if total else None,
        "by_source": by_source,
        "by_class": by_class,
        "by_status": [(label, statuses.get(value, 0)) for value, label in Inquiry.Status.choices],
        "lost": [(label, lost.get(value, 0)) for value, label in Inquiry.LostReason.choices if lost.get(value)],
    }
