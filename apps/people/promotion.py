"""Moving students into the next academic session (M4): promote, keep in the same class, or graduate.

Nothing changes in the current session; each decision makes the student's enrolment for the next one.
"""

from django.db import transaction

from apps.academics.models import ClassLevel, Section
from apps.organisation.models import AcademicSession

from .models import Enrolment, Student

PROMOTE, KEEP, GRADUATE, SKIP = "promote", "keep", "graduate", "skip"
LAST_CLASS = "class-10"
NO_NEXT_CLASS = {"hifz"}  # Hifz students move on when they finish, not by year


def next_session(current):
    if current is None:
        return None
    return AcademicSession.objects.filter(starts_on__gt=current.starts_on).order_by("starts_on").first()


def next_level(level):
    """The class after this one (Play Group → Nursery → … → Class 10). None after Class 10 and for Hifz."""
    if level.code in NO_NEXT_CLASS or level.code == LAST_CLASS:
        return None
    return (
        ClassLevel.objects.filter(is_active=True, sort_order__gt=level.sort_order)
        .exclude(code__in=NO_NEXT_CLASS)
        .order_by("sort_order")
        .first()
    )


def default_action(level):
    if level.code == LAST_CLASS:
        return GRADUATE
    return KEEP if level.code in NO_NEXT_CLASS else PROMOTE


@transaction.atomic
def copy_sections(branch, current, upcoming):
    """Next session gets the same sections as this one (class, name, boys/girls, campus, capacity).
    Class teachers are not copied: they are chosen again. Sections already there are left alone."""
    made = 0
    for section in Section.objects.filter(branch=branch, session=current, is_active=True):
        _obj, created = Section.objects.get_or_create(
            branch=branch,
            session=upcoming,
            class_level=section.class_level,
            name=section.name,
            defaults={
                "gender_group": section.gender_group,
                "campus": section.campus,
                "capacity": section.capacity,
            },
        )
        made += created
    return made


def target_section(section, action, upcoming):
    """Where a student of `section` goes next session: same section name in the next class (promote)
    or in the same class (keep)."""
    level = next_level(section.class_level) if action == PROMOTE else section.class_level
    if level is None:
        return None
    return Section.objects.filter(
        branch_id=section.branch_id, session=upcoming, class_level=level, name=section.name
    ).first()


@transaction.atomic
def apply(section, upcoming, decisions, user):
    """`decisions` = {student_id: (action, target_section or None)}. Returns counts per action."""
    counts = {PROMOTE: 0, KEEP: 0, GRADUATE: 0, SKIP: 0}
    for student_id, (action, target) in decisions.items():
        student = Student.objects.get(pk=student_id, branch_id=section.branch_id)
        if action == GRADUATE:
            student.status = Student.Status.GRADUATED
            student.status_changed_on = upcoming.starts_on
            student.save(update_fields=["status", "status_changed_on"])
        elif action in (PROMOTE, KEEP) and target is not None:
            enrolment = Enrolment.objects.filter(student=student, session=upcoming).first() or Enrolment(
                student=student, session=upcoming, branch_id=student.branch_id
            )
            enrolment.section, enrolment.roll_no = target, None
            enrolment.full_clean()
            enrolment.save()
        else:
            action = SKIP
        counts[action] += 1
    return counts
