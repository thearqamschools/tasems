"""Result calculation for the approved pattern. Ordinary arithmetic, fully tested — no AI.

Every figure on a result card comes from here, so this is the one place to check.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.utils.translation import gettext as _

from apps.academics.models import CurriculumSubject
from apps.attendance.models import AttendanceRecord, Status
from apps.people.models import Enrolment, Student

from .models import Exam, GradingComponent, GradingScheme, Mark, Paper, Rating

HUNDRED = Decimal(100)
TWO = Decimal("0.01")
Source = GradingComponent.Source


def q2(value):
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def plain(value):
    """30.00 → "30", 27.50 → "27.5" (never scientific notation)."""
    text = format(Decimal(value).normalize(), "f")
    return text


def grade_for(scheme, percent):
    for band in sorted(scheme.bands, key=lambda b: b["min"], reverse=True):
        if percent >= Decimal(str(band["min"])):
            return band["grade"]
    return ""


def attendance_points(scheme, component, percent):
    table = sorted(scheme.attendance_points, key=lambda row: row[0], reverse=True)
    top = Decimal(str(max(points for _min, points in table))) or Decimal(1)
    for minimum, points in table:
        if percent >= Decimal(str(minimum)):
            return q2(Decimal(str(points)) * component.max_marks / top)
    return Decimal(0)


@dataclass
class Part:
    value: Decimal | None = None
    raw: str = ""  # e.g. "60 / 80" for exam papers
    note: str = ""


@dataclass
class SubjectResult:
    subject: object
    parts: dict = field(default_factory=dict)  # component code → Part
    score: Decimal | None = None
    exam_percent: Decimal | None = None
    grade: str = ""
    passed: bool | None = None
    missing: list = field(default_factory=list)  # component names still to be entered
    raw_obtained: Decimal | None = None  # Mid-Term card: marks as written on the paper
    raw_total: int | None = None


@dataclass
class StudentResult:
    student: Student
    enrolment: Enrolment
    subjects: list = field(default_factory=list)
    percent: Decimal | None = None
    obtained: Decimal | None = None
    maximum: Decimal | None = None
    grade: str = ""
    complete: bool = False
    failed_subjects: list = field(default_factory=list)
    position: int | None = None
    attendance_days: int = 0
    present_days: int = 0
    attendance_percent: Decimal | None = None
    discipline: Part | None = None

    @property
    def passed(self):
        return self.complete and not self.failed_subjects


def exam_for(section, kind):
    return (
        Exam.objects.filter(session=section.session, kind=kind)
        .filter(Q(branch__isnull=True) | Q(branch=section.branch_id))
        .order_by("-starts_on", "-id")
        .first()
    )


def _subject_order(section, papers):
    subjects = {p.subject_id: p.subject for p in papers}
    mapped = list(
        CurriculumSubject.objects.filter(class_level=section.class_level)
        .order_by("sort_order")
        .values_list("subject_id", flat=True)
    )
    ordered = [subjects[s] for s in mapped if s in subjects]
    ordered += sorted((s for sid, s in subjects.items() if sid not in mapped), key=lambda s: s.name)
    return ordered


def _paper_pct(mark, paper):
    if mark is None or mark.status != Mark.Status.PRESENT or mark.obtained is None:
        return None
    return Decimal(mark.obtained) * HUNDRED / Decimal(paper.total_marks)


def section_results(section, card="annual"):
    """Results for every active student of a section. `card` is "mid" or "annual"."""
    scheme = GradingScheme.for_stage(section.class_level.stage)
    components = list(scheme.components.all()) if scheme else []
    mid_exam = exam_for(section, Exam.Kind.MID)
    final_exam = exam_for(section, Exam.Kind.FINAL) if card == "annual" else None
    exams = [e for e in (mid_exam, final_exam) if e]
    papers = list(
        Paper.objects.filter(exam__in=exams, class_level=section.class_level).select_related("subject", "exam")
    )
    enrolments = list(
        Enrolment.objects.filter(section=section, session=section.session, student__status=Student.Status.ACTIVE)
        .select_related("student")
        .order_by("roll_no", "student__first_name")
    )
    ids = [e.student_id for e in enrolments]
    marks = {(m.paper_id, m.student_id): m for m in Mark.objects.filter(paper__in=papers, student_id__in=ids)}
    ratings = {
        (r.student_id, r.component_id, r.subject_id): r.value
        for r in Rating.objects.filter(student_id__in=ids, session=section.session, component__in=components)
    }
    attendance = defaultdict(lambda: [0, 0])
    for student_id, status in AttendanceRecord.objects.filter(
        student_id__in=ids, date__gte=section.session.starts_on, date__lte=section.session.ends_on
    ).values_list("student_id", "status"):
        attendance[student_id][0] += 1
        if status in (Status.PRESENT, Status.LATE):
            attendance[student_id][1] += 1

    paper_of = {}
    for p in papers:
        kind = "mid" if mid_exam and p.exam_id == mid_exam.id else "final"
        paper_of[(kind, p.subject_id)] = p
    subjects = _subject_order(section, papers)
    discipline = next((c for c in components if c.source == Source.RATING and c.scope == "student"), None)

    results = []
    for e in enrolments:
        r = StudentResult(student=e.student, enrolment=e)
        r.attendance_days, r.present_days = attendance[e.student_id]
        if r.attendance_days:
            r.attendance_percent = q2(Decimal(r.present_days) * HUNDRED / Decimal(r.attendance_days))
        if discipline:
            value = ratings.get((e.student_id, discipline.id, None))
            r.discipline = Part(value=value)
        complete = bool(subjects) and scheme is not None
        for subject in subjects:
            if card == "mid":
                s = _mid_subject(scheme, subject, paper_of.get(("mid", subject.id)), marks, e.student_id)
            else:
                s = _annual_subject(scheme, components, subject, paper_of, marks, ratings, r, e.student_id)
            if s.score is None:
                complete = False
            else:
                s.grade = grade_for(scheme, s.score)
                if not s.passed:
                    r.failed_subjects.append(subject)
            r.subjects.append(s)
        r.complete = complete
        if complete and card == "mid":
            # Mid-Term report: actual marks out of the actual paper totals.
            r.maximum = Decimal(sum(s.raw_total for s in r.subjects))
            r.obtained = q2(sum(s.raw_obtained for s in r.subjects))
            r.percent = q2(r.obtained * HUNDRED / r.maximum)
            r.grade = grade_for(scheme, r.percent)
        elif complete:
            r.maximum = HUNDRED * len(subjects)
            r.obtained = q2(sum(s.score for s in r.subjects))
            r.percent = q2(r.obtained * HUNDRED / r.maximum)
            r.grade = grade_for(scheme, r.percent)
        results.append(r)

    if scheme:
        _assign_positions(results, scheme)
    return {
        "scheme": scheme,
        "components": components if card == "annual" else [],
        "results": results,
        "subjects": subjects,
        "mid_exam": mid_exam,
        "final_exam": final_exam,
    }


def _mid_subject(scheme, subject, paper, marks, student_id):
    s = SubjectResult(subject=subject)
    mark = marks.get((paper.id, student_id)) if paper else None
    pct = _paper_pct(mark, paper) if paper else None
    part = Part(raw=f"{plain(mark.obtained)} / {paper.total_marks}" if pct is not None else "")
    if mark is not None and mark.status != Mark.Status.PRESENT:
        part.note = mark.get_status_display()
        pct = Decimal(0) if mark.status == Mark.Status.ABSENT else None
    s.parts["mid"] = part
    if pct is None:
        s.missing.append(_("Mid-Term marks"))
        return s
    s.raw_obtained = Decimal(mark.obtained) if mark.status == Mark.Status.PRESENT else Decimal(0)
    s.raw_total = paper.total_marks
    s.score = s.exam_percent = q2(pct)
    s.passed = s.score >= scheme.pass_percent
    return s


def _annual_subject(scheme, components, subject, paper_of, marks, ratings, r, student_id):
    s = SubjectResult(subject=subject)
    by_source = {c.source: c for c in components if c.is_exam}
    final_c, mid_c = by_source.get(Source.FINAL), by_source.get(Source.MID)
    exam_value, exam_max, final_share = Decimal(0), Decimal(0), None

    # Mid-Term first: an excused absence moves its share to the Final.
    if mid_c:
        paper = paper_of.get(("mid", subject.id))
        mark = marks.get((paper.id, student_id)) if paper else None
        part = Part()
        if paper is None:
            part.note = _("No Mid-Term paper")
            final_share = mid_c.max_marks
        elif mark is None:
            s.missing.append(mid_c.name)
        elif mark.status == Mark.Status.PRESENT:
            part.value = q2(_paper_pct(mark, paper) * mid_c.max_marks / HUNDRED)
            part.raw = f"{plain(mark.obtained)} / {paper.total_marks}"
        elif mark.status == Mark.Status.EXCUSED and scheme.absent_mid_rule == GradingScheme.AbsentMid.FINAL_COVERS:
            part.note = _("Leave — Final counts")
            final_share = mid_c.max_marks
        else:
            part.value = Decimal(0)
            part.note = mark.get_status_display()
        s.parts[mid_c.code] = part
        if part.value is not None:
            exam_value += part.value
            exam_max += mid_c.max_marks

    if final_c:
        paper = paper_of.get(("final", subject.id))
        mark = marks.get((paper.id, student_id)) if paper else None
        share = final_c.max_marks + (final_share or 0)
        part = Part()
        if paper is None or mark is None:
            s.missing.append(final_c.name)
        elif mark.status == Mark.Status.PRESENT:
            pct = _paper_pct(mark, paper)
            part.value = q2(pct * share / HUNDRED)
            part.raw = f"{plain(mark.obtained)} / {paper.total_marks}"
        elif mark.status == Mark.Status.EXCUSED:
            part.note = mark.get_status_display()
            s.missing.append(final_c.name)  # needs a re-sit before an annual result
        else:
            part.value = Decimal(0)
            part.note = mark.get_status_display()
        s.parts[final_c.code] = part
        if part.value is not None:
            exam_value += part.value
            exam_max += share

    for c in components:
        if c.is_exam:
            continue
        part = Part()
        if c.source == Source.ATTENDANCE:
            if r.attendance_percent is None:
                s.missing.append(c.name)
            else:
                part.value = attendance_points(scheme, c, r.attendance_percent)
        else:
            value = ratings.get((student_id, c.id, None if c.scope == "student" else subject.id))
            if value is None:
                s.missing.append(c.name)
            else:
                part.value = q2(value)
        s.parts[c.code] = part

    if s.missing:
        return s
    s.score = q2(sum(p.value for p in s.parts.values() if p.value is not None))
    s.exam_percent = q2(exam_value * HUNDRED / exam_max) if exam_max else Decimal(0)
    s.passed = s.score >= scheme.pass_percent and s.exam_percent >= scheme.exam_pass_percent
    return s


def _assign_positions(results, scheme):
    if scheme.positions == GradingScheme.Positions.NONE:
        return
    ranked = sorted((r for r in results if r.complete), key=lambda r: r.percent, reverse=True)
    position, previous = 0, None
    for index, r in enumerate(ranked, start=1):
        if r.percent != previous:
            position, previous = index, r.percent  # equal percentages share a position
        if scheme.positions == GradingScheme.Positions.ALL or position <= 3:
            r.position = position
