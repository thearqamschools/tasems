"""Students needing attention (M13, free part): simple, visible rules over records TASEMS already keeps.

No AI and no outside service: each signal is a plain rule with a limit the school can change on the page. The
limits below are starting values only, to be confirmed by head office."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Count, Q, Sum
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.attendance.models import AttendanceRecord
from apps.people.models import Enrolment, Student

DEFAULTS = {
    "streak": 3,  # absent this many school days in a row (leave does not count)
    "attendance": 75,  # attendance % over the last 30 days below this
    "drop": 10,  # exam % fell by at least this many points since the previous exam
    "fee_months": 2,  # monthly fee unpaid for at least this many months
    "not_ready": 3,  # Hifz sabaq not ready at least this many times in 14 days
}
LIMITS = {"streak": (2, 30), "attendance": (1, 100), "drop": (1, 100), "fee_months": (1, 24), "not_ready": (1, 14)}
MIN_DAYS = 5  # fewer register days than this in 30 days: too early to judge attendance


@dataclass
class Row:
    student: Student
    section: object
    flags: list = field(default_factory=list)  # (code, text)
    phone: str = ""


def read_limits(params):
    out = {}
    for key, default in DEFAULTS.items():
        lo, hi = LIMITS[key]
        try:
            out[key] = min(max(int(params.get(key, default)), lo), hi)
        except (TypeError, ValueError):
            out[key] = default
    return out


def _absences(student_ids, today, limits):
    """{student_id: [(code, text)]} for absence streaks and low attendance in the last 30 days."""
    start = today - dt.timedelta(days=30)
    by_student = defaultdict(list)
    for sid, status in (
        AttendanceRecord.objects.filter(student_id__in=student_ids, date__gt=start, date__lte=today)
        .order_by("student_id", "-date")
        .values_list("student_id", "status")
    ):
        by_student[sid].append(status)
    out = defaultdict(list)
    for sid, statuses in by_student.items():
        streak = 0
        for s in statuses:
            if s != "absent":
                break
            streak += 1
        if streak >= limits["streak"]:
            out[sid].append(("streak", _("Absent %(n)s days in a row") % {"n": streak}))
        if len(statuses) >= MIN_DAYS:
            rate = round(100 * sum(1 for s in statuses if s in ("present", "late")) / len(statuses))
            if rate < limits["attendance"]:
                out[sid].append(("attendance", _("Attendance %(p)s in the last 30 days") % {"p": f"{rate}%"}))
    return out


def exam_percentages(student_ids):
    """{student_id: [(exam, percent)]} oldest exam first, from marks entered (present papers only)."""
    from apps.exams.models import Mark

    rows = (
        Mark.objects.filter(student_id__in=student_ids, status=Mark.Status.PRESENT, obtained__isnull=False)
        .values("student_id", "paper__exam_id")
        .annotate(got=Sum("obtained"), total=Sum("paper__total_marks"))
    )
    from apps.exams.models import Exam

    exams = Exam.objects.in_bulk({r["paper__exam_id"] for r in rows})
    out = defaultdict(list)
    for r in rows:
        if r["total"]:
            out[r["student_id"]].append((exams[r["paper__exam_id"]], round(float(100 * r["got"] / r["total"]), 1)))
    for sid in out:
        out[sid].sort(key=lambda x: (x[0].starts_on or dt.date.min, x[0].pk))
    return out


def _marks(student_ids, limits):
    from apps.exams.models import GradingScheme

    scheme = GradingScheme.objects.filter(is_default=True).first()
    pass_mark = float(scheme.exam_pass_percent) if scheme else None
    out = defaultdict(list)
    for sid, series in exam_percentages(student_ids).items():
        exam, latest = series[-1]
        if pass_mark is not None and latest < pass_mark:
            out[sid].append(
                ("below_pass", _("%(p)s in %(exam)s (pass mark %(m)s)") % {
                    "p": f"{latest:g}%", "exam": exam.name, "m": f"{pass_mark:g}%"})
            )  # fmt: skip
        if len(series) > 1:
            before = series[-2][1]
            if before - latest >= limits["drop"]:
                out[sid].append(
                    ("drop", _("Marks fell from %(a)s to %(b)s") % {"a": f"{before:g}%", "b": f"{latest:g}%"})
                )
    return out


def _fees(branch, student_ids, today, limits):
    from apps.core.templatetags.tasems_tags import rupees
    from apps.fees.models import month_start
    from apps.fees.reports import outstanding

    out = defaultdict(list)
    for r in outstanding(branch, as_of=month_start(today), student_ids=student_ids):
        if r["months"] >= limits["fee_months"]:
            out[r["student_id"]].append(
                (
                    "fees",
                    ngettext(
                        "%(n)s month's fee unpaid (Rs %(due)s)", "%(n)s months' fee unpaid (Rs %(due)s)", r["months"]
                    )
                    % {"n": r["months"], "due": rupees(r["due"])},
                )
            )
    return out


def _hifz(student_ids, today, limits):
    from apps.hifz.models import HifzLesson

    out = defaultdict(list)
    for r in (
        HifzLesson.objects.filter(student_id__in=student_ids, date__gt=today - dt.timedelta(days=14), date__lte=today)
        .values("student_id")
        .annotate(n=Count("id", filter=Q(status=HifzLesson.Status.NOT_READY)))
        .filter(n__gte=limits["not_ready"])
    ):
        out[r["student_id"]].append(
            (
                "not_ready",
                ngettext("Sabaq not ready once in 14 days", "Sabaq not ready %(n)s times in 14 days", r["n"])
                % {"n": r["n"]},
            )
        )
    return out


def signals(can_fees, can_hifz):
    out = [
        ("streak", _("Absent days in a row")),
        ("attendance", _("Low attendance")),
        ("below_pass", _("Below the pass mark")),
        ("drop", _("Falling marks")),
    ]
    if can_fees:
        out.append(("fees", _("Fee unpaid")))
    if can_hifz:
        out.append(("not_ready", _("Hifz sabaq not ready")))
    return out


def students_needing_attention(branch, session, today, limits, sections=None, can_fees=False, can_hifz=False):
    """Active students of the branch (or of `sections`) with at least one signal, most signals first."""
    if session is None:
        return []
    enrolments = Enrolment.objects.filter(
        branch=branch, session=session, student__status=Student.Status.ACTIVE
    ).select_related("student", "section__class_level")
    if sections is not None:
        enrolments = enrolments.filter(section__in=sections)
    enrolments = list(enrolments)
    ids = [e.student_id for e in enrolments]
    found = defaultdict(list)
    parts = [_absences(ids, today, limits), _marks(ids, limits)]
    if can_fees:
        parts.append(_fees(branch, ids, today, limits))
    if can_hifz:
        parts.append(_hifz(ids, today, limits))
    for part in parts:
        for sid, flags in part.items():
            found[sid].extend(flags)
    rows = [Row(e.student, e.section, found[e.student_id]) for e in enrolments if found.get(e.student_id)]
    from apps.fees.reports import guardian_phones

    phones = guardian_phones([r.student.id for r in rows])
    for r in rows:
        r.phone = phones.get(r.student.id, "")
    rows.sort(key=lambda r: (-len(r.flags), r.section.class_level.sort_order, r.section.name, r.student.full_name))
    return rows
