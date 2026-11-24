"""Subject teachers and the class timetable (M7).

A cell of a timetable holds only the subject; its teacher is the section's teacher for that subject. A teacher
cannot be in two classes in the same period: saving a timetable that would do that is refused, and a clash
caused later (by changing a subject's teacher) is shown on the timetable pages."""

from collections import defaultdict

from django.db import transaction
from django.utils.translation import gettext as _

from apps.core.models import AuditEvent

from .models import WEEKDAYS, CurriculumSubject, Period, SectionSubject, TimetableEntry
from .teachers import teacher_key, teacher_name


def teachers_of(branch):
    """The choices for a class or subject teacher: the branch's teachers and Qaris from the staff records, with or
    without a login (R17-8)."""
    from .teachers import teacher_choices

    return teacher_choices(branch)


def subjects_of(section):
    """The class's subjects (curriculum order) plus any other subject already given to the section,
    with the teacher of each: [(subject, teacher or None)]."""
    from .teachers import teacher_of

    assigned = {s.subject_id: s for s in section.subject_teachers.select_related("subject", "teacher", "teacher_staff")}
    rows = []
    for cs in CurriculumSubject.objects.filter(class_level=section.class_level).select_related("subject"):
        ss = assigned.pop(cs.subject_id, None)
        rows.append((cs.subject, teacher_of(ss)))
    rows += [(ss.subject, teacher_of(ss)) for ss in assigned.values()]
    return rows


@transaction.atomic
def save_subject_teachers(section, teachers, user):
    """`teachers` = {subject: staff record or None}. Records only what changed; the login follows the staff record."""
    current = {s.subject_id: s for s in section.subject_teachers.all()}
    changes = {}
    for subject, teacher in teachers.items():
        ss = current.get(subject.id)
        old = (ss.teacher_staff_id, None if ss.teacher_staff_id else ss.teacher_id) if ss else (None, None)
        new = (teacher.id if teacher else None, None)
        if ss and old[1] and teacher is not None and teacher.user_id == old[1]:
            old = new  # the same person, chosen before by their login
        if old == new:
            continue
        login = teacher.user if teacher is not None and teacher.user_id else None
        if ss:
            ss.teacher_staff, ss.teacher = teacher, login
            ss.save(update_fields=["teacher_staff", "teacher", "updated_at"])
        else:
            SectionSubject.objects.create(
                branch_id=section.branch_id, section=section, subject=subject, teacher_staff=teacher, teacher=login
            )
        changes[subject.name] = {"from": old[0] or old[1], "to": new[0]}
    if changes:
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.UPDATE,
            model_label="academics.SectionSubject",
            object_id=str(section.pk),
            object_repr=f"{section} subject teachers"[:255],
            branch_id=section.branch_id,
            changes=changes,
        )
    return changes


def days_of(section):
    return [d for d in WEEKDAYS if d[0] < 5 or section.class_level.attends_on_saturday]


def _teacher_map(sections):
    """{(section_id, subject_id): teacher}"""
    from django.db.models import Q

    from .teachers import teacher_of

    return {
        (s.section_id, s.subject_id): teacher_of(s)
        for s in SectionSubject.objects.filter(section__in=sections)
        .filter(Q(teacher__isnull=False) | Q(teacher_staff__isnull=False))
        .select_related("teacher", "teacher_staff")
    }


def grid(section):
    periods = list(Period.objects.filter(branch_id=section.branch_id))
    entries = {(e.weekday, e.period_id): e for e in section.timetable.select_related("subject", "period")}
    teachers = _teacher_map([section])
    rows = []
    for p in periods:
        cells = []
        for day, _label in days_of(section):
            e = None if p.is_break else entries.get((day, p.id))
            cells.append({"day": day, "entry": e, "teacher": teachers.get((section.id, e.subject_id)) if e else None})
        rows.append({"period": p, "cells": cells})
    return {"days": days_of(section), "rows": rows, "periods": periods}


def clashes(branch, session):
    """Teachers placed in two classes in the same period: [(teacher, day label, period, [entries])]."""
    from .models import Section

    sections = Section.objects.filter(branch=branch, session=session)
    teachers = _teacher_map(sections)
    slots = defaultdict(list)
    for e in TimetableEntry.objects.filter(section__in=sections).select_related(
        "section__class_level", "period", "subject"
    ):
        t = teachers.get((e.section_id, e.subject_id))
        if t:
            slots[(teacher_key(t), e.weekday, e.period_id)].append((t, e))
    days = dict(WEEKDAYS)
    return [
        (items[0][0], days[e_day], items[0][1].period, [e for _t, e in items])
        for (_tid, e_day, _pid), items in sorted(slots.items(), key=lambda kv: (kv[0][1], kv[1][0][1].period.number))
        if len(items) > 1
    ]


@transaction.atomic
def save_grid(section, cells, user):
    """`cells` = {(weekday, period_id): subject or None}. Refuses (ValueError) a teacher double-booked
    with another class of the same session; otherwise replaces the section's timetable."""
    from .models import Section

    teachers = _teacher_map([section])
    others = Section.objects.filter(branch_id=section.branch_id, session_id=section.session_id).exclude(pk=section.pk)
    other_teachers = _teacher_map(others)
    busy = {}
    for e in TimetableEntry.objects.filter(section__in=others).select_related("section__class_level"):
        t = other_teachers.get((e.section_id, e.subject_id))
        if t:
            busy[(teacher_key(t), e.weekday, e.period_id)] = e.section
    problems = []
    days = dict(WEEKDAYS)
    periods = {p.id: p for p in Period.objects.filter(branch_id=section.branch_id)}
    for (day, period_id), subject in cells.items():
        if subject is None:
            continue
        t = teachers.get((section.id, subject.id))
        other = busy.get((teacher_key(t), day, period_id)) if t else None
        if other:
            problems.append(
                _("%(t)s already teaches %(s)s on %(d)s, %(p)s.")
                % {"t": teacher_name(t), "s": other, "d": days[day], "p": periods[period_id]}
            )
    if problems:
        raise ValueError(problems)
    section.timetable.all().delete()
    TimetableEntry.objects.bulk_create(
        TimetableEntry(branch_id=section.branch_id, section=section, weekday=day, period_id=pid, subject=subject)
        for (day, pid), subject in cells.items()
        if subject is not None
    )
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.UPDATE,
        model_label="academics.TimetableEntry",
        object_id=str(section.pk),
        object_repr=f"{section} timetable"[:255],
        branch_id=section.branch_id,
        changes={"cells": sum(1 for s in cells.values() if s)},
    )


def teacher_grid(branch, session, teacher):
    """The teacher's week: each period and day with the class and subject they teach."""
    from django.db.models import Q

    from apps.hr.models import Employee

    from .models import Section

    who = Q(teacher_staff=teacher) if isinstance(teacher, Employee) else Q(teacher=teacher)
    if isinstance(teacher, Employee) and teacher.user_id:
        who |= Q(teacher_id=teacher.user_id)
    assigned = SectionSubject.objects.filter(who, branch=branch, section__session=session, section__is_active=True)
    assigned = assigned.values_list("section_id", "subject_id")
    pairs = set(assigned)
    sections = Section.objects.filter(pk__in={s for s, _sub in pairs})
    entries = defaultdict(list)
    for e in TimetableEntry.objects.filter(section__in=sections).select_related("section__class_level", "subject"):
        if (e.section_id, e.subject_id) in pairs:
            entries[(e.weekday, e.period_id)].append(e)
    periods = list(Period.objects.filter(branch=branch))
    days = [d for d in WEEKDAYS if d[0] < 5 or any(day == 5 for day, _p in entries)]
    rows = [{"period": p, "cells": [entries.get((d, p.id), []) for d, _l in days]} for p in periods]
    count = sum(len(v) for v in entries.values())
    return {"days": days, "rows": rows, "periods": periods, "count": count, "pairs": len(pairs)}
