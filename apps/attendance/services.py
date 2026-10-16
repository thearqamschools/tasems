"""Rules for taking the daily register."""

import datetime as dt
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.people.models import Enrolment, Student

from .models import AttendanceRecord, SectionAttendance, Status

CHANGE_PERM = "attendance.change_attendancerecord"
MARK_PERM = "attendance.add_attendancerecord"
VIEW_PERM = "attendance.view_attendancerecord"


def roster(section):
    """Enrolments of active students in this section, in roll-number order."""
    return list(
        Enrolment.objects.filter(section=section, session_id=section.session_id, student__status=Student.Status.ACTIVE)
        .select_related("student")
        .order_by("roll_no", "student__first_name", "student__last_name")
    )


def can_mark(user, section, date):
    """Teachers mark their own sections for today; principals and coordinators can mark or
    correct any section of their branch for any past day of the session."""
    today = timezone.localdate()
    if date > today or date < section.session.starts_on or date > section.session.ends_on:
        return False
    if user.has_branch_perm(CHANGE_PERM, section.branch_id):
        return True
    return date == today and section.class_teacher_id == user.id and user.has_branch_perm(MARK_PERM, section.branch_id)


@transaction.atomic
def save_register(section, date, marks, user):
    """`marks` maps student id → (status, note). Every rostered student must be included.

    Returns the SectionAttendance. Changes to an already-taken register are written to
    the audit log student by student.
    """
    entries = {e.student_id: e for e in roster(section)}
    if set(marks) != set(entries):
        raise ValueError("The register must cover exactly the students in this section.")
    for status, _note in marks.values():
        if status not in Status.values:
            raise ValueError(f"Unknown status {status!r}")

    existing = {r.student_id: r for r in AttendanceRecord.objects.filter(student_id__in=marks, date=date)}
    changes = {}
    for student_id, (status, _note) in marks.items():
        old = existing.get(student_id)
        if old and old.status != status:
            changes[str(student_id)] = {"from": old.status, "to": status}

    AttendanceRecord.objects.bulk_create(
        [
            AttendanceRecord(
                branch_id=section.branch_id,
                student_id=student_id,
                section=section,
                date=date,
                status=status,
                note=note[:200],
                marked_by=user,
            )
            for student_id, (status, note) in marks.items()
        ],
        update_conflicts=True,
        unique_fields=["student", "date"],
        update_fields=["status", "note", "section", "marked_by", "updated_at"],
    )

    counts = defaultdict(int)
    for status, _note in marks.values():
        counts[status] += 1
    register, _created = SectionAttendance.objects.update_or_create(
        section=section,
        date=date,
        defaults={
            "branch_id": section.branch_id,
            "taken_by": user,
            "present": counts[Status.PRESENT],
            "absent": counts[Status.ABSENT],
            "leave": counts[Status.LEAVE],
            "late": counts[Status.LATE],
        },
    )
    if changes:
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.UPDATE,
            model_label="attendance.AttendanceRecord",
            object_id=f"{section.pk}:{date.isoformat()}",
            object_repr=f"Attendance {section} {date.isoformat()}",
            branch_id=section.branch_id,
            changes=changes,
        )
    return register


def absence_streaks(student_ids, date, days=14):
    """How many school days in a row (ending on `date`) each student has been absent."""
    since = date - dt.timedelta(days=days * 2)
    history = defaultdict(list)
    for student_id, _day, status in (
        AttendanceRecord.objects.filter(student_id__in=student_ids, date__gte=since, date__lte=date)
        .order_by("student_id", "-date")
        .values_list("student_id", "date", "status")
    ):
        history[student_id].append(status)
    streaks = {}
    for student_id in student_ids:
        run = 0
        for status in history.get(student_id, []):
            if status != Status.ABSENT:
                break
            run += 1
        streaks[student_id] = run
    return streaks
