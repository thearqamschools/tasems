"""Marks entry rules."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.people.models import Enrolment, Student

from .models import Mark

ADD_PERM = "exams.add_mark"
CHANGE_PERM = "exams.change_mark"
VIEW_PERM = "exams.view_mark"


def can_enter(user, section, exam):
    """Class teachers enter their own section's marks until the due date and before results are
    published; principals and coordinators can enter or correct marks at any time."""
    if user.has_branch_perm(CHANGE_PERM, section.branch_id):
        return True
    if exam.is_published or section.class_teacher_id != user.id:
        return False
    if exam.marks_due_on and timezone.localdate() > exam.marks_due_on:
        return False
    return user.has_branch_perm(ADD_PERM, section.branch_id)


def roster(section):
    return list(
        Enrolment.objects.filter(section=section, session_id=section.session_id, student__status=Student.Status.ACTIVE)
        .select_related("student")
        .order_by("roll_no", "student__first_name")
    )


def parse_marks(raw, total):
    """Returns Decimal marks, or raises ValueError with a message for the teacher."""
    text = (raw or "").strip()
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("not a number") from exc
    if value < 0 or value > total:
        raise ValueError(f"must be between 0 and {total}")
    if value * 2 != (value * 2).to_integral_value():
        raise ValueError("use whole or half marks")
    return value


@transaction.atomic
def save_marks(paper, section, entries, user):
    """`entries` maps student id → (status, Decimal or None). Blank present marks are skipped (not yet entered).
    Changes to marks already saved are written to the audit log."""
    existing = {m.student_id: m for m in Mark.objects.filter(paper=paper, student_id__in=entries)}
    changes, rows = {}, []
    for student_id, (status, obtained) in entries.items():
        if status == Mark.Status.PRESENT and obtained is None:
            continue
        if status != Mark.Status.PRESENT:
            obtained = None
        old = existing.get(student_id)
        if old and (old.status != status or old.obtained != obtained):
            changes[str(student_id)] = {
                "from": f"{old.obtained if old.obtained is not None else old.status}",
                "to": f"{obtained if obtained is not None else status}",
            }
        rows.append(
            Mark(
                branch_id=section.branch_id,
                paper=paper,
                student_id=student_id,
                section=section,
                obtained=obtained,
                status=status,
                entered_by=user,
            )
        )
    Mark.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["paper", "student"],
        update_fields=["obtained", "status", "section", "entered_by", "updated_at"],
    )
    if changes:
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.UPDATE,
            model_label="exams.Mark",
            object_id=f"{paper.pk}:{section.pk}",
            object_repr=f"Marks {paper} {section}",
            branch_id=section.branch_id,
            changes=changes,
        )
    return len(rows)
