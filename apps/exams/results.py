"""Result calculation. Ordinary arithmetic, fully tested — no AI involved.

Every figure on a result card comes from here, so it is one place to check.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

from apps.academics.models import CurriculumSubject
from apps.attendance.models import AttendanceRecord, Status
from apps.people.models import Enrolment, Student

from .models import Exam, GradingScheme, Mark, Paper

HUNDRED = Decimal(100)
TWO = Decimal("0.01")


def q2(value):
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def grade_for(scheme, percent):
    for band in sorted(scheme.bands, key=lambda b: b["min"], reverse=True):
        if percent >= Decimal(str(band["min"])):
            return band["grade"]
    return scheme.bands[-1]["grade"] if scheme.bands else ""


@dataclass
class SubjectResult:
    subject: object
    mid: Mark | None = None
    mid_paper: Paper | None = None
    final: Mark | None = None
    final_paper: Paper | None = None
    test_percent: Decimal | None = None
    score: Decimal | None = None  # out of 100
    grade: str = ""
    passed: bool | None = None
    note: str = ""


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


def _pct(mark, paper):
    if mark is None or mark.status != Mark.Status.PRESENT or mark.obtained is None:
        return None
    return Decimal(mark.obtained) * HUNDRED / Decimal(paper.total_marks)


def _subject_order(section, papers):
    mapped = list(
        CurriculumSubject.objects.filter(class_level=section.class_level)
        .order_by("sort_order")
        .values_list("subject_id", flat=True)
    )
    subjects = {p.subject_id: p.subject for p in papers}
    ordered = [subjects[s] for s in mapped if s in subjects]
    ordered += sorted((s for sid, s in subjects.items() if sid not in mapped), key=lambda s: s.name)
    return ordered


def section_results(section, card="annual"):
    """Results for every active student in a section. `card` is "mid" or "annual"."""
    scheme = GradingScheme.for_stage(section.class_level.stage)
    mid_exam = exam_for(section, Exam.Kind.MID)
    final_exam = exam_for(section, Exam.Kind.FINAL) if card == "annual" else None
    test_exams = []
    if card == "annual" and scheme.test_weight:
        test_exams = list(
            Exam.objects.filter(session=section.session, kind=Exam.Kind.TEST).filter(
                Q(branch__isnull=True) | Q(branch=section.branch_id)
            )
        )
    exams = [e for e in [mid_exam, final_exam, *test_exams] if e]
    papers = list(
        Paper.objects.filter(exam__in=exams, class_level=section.class_level).select_related("subject", "exam")
    )
    enrolments = list(
        Enrolment.objects.filter(section=section, session=section.session, student__status=Student.Status.ACTIVE)
        .select_related("student")
        .order_by("roll_no", "student__first_name")
    )
    marks = {
        (m.paper_id, m.student_id): m
        for m in Mark.objects.filter(paper__in=papers, student_id__in=[e.student_id for e in enrolments])
    }
    attendance = defaultdict(lambda: [0, 0])
    for student_id, status in AttendanceRecord.objects.filter(
        student_id__in=[e.student_id for e in enrolments], date__gte=section.session.starts_on
    ).values_list("student_id", "status"):
        attendance[student_id][0] += 1
        if status in (Status.PRESENT, Status.LATE):
            attendance[student_id][1] += 1

    by_subject = defaultdict(dict)
    tests_by_subject = defaultdict(list)
    for p in papers:
        if mid_exam and p.exam_id == mid_exam.id:
            by_subject[p.subject_id]["mid"] = p
        elif final_exam and p.exam_id == final_exam.id:
            by_subject[p.subject_id]["final"] = p
        else:
            tests_by_subject[p.subject_id].append(p)
    subjects = _subject_order(section, papers)

    results = []
    for e in enrolments:
        r = StudentResult(student=e.student, enrolment=e)
        r.attendance_days, r.present_days = attendance[e.student_id]
        complete = bool(subjects)
        for subject in subjects:
            s = SubjectResult(subject=subject)
            s.mid_paper = by_subject[subject.id].get("mid")
            s.final_paper = by_subject[subject.id].get("final")
            s.mid = marks.get((s.mid_paper.id, e.student_id)) if s.mid_paper else None
            s.final = marks.get((s.final_paper.id, e.student_id)) if s.final_paper else None
            if card == "mid":
                pct = _pct(s.mid, s.mid_paper) if s.mid_paper else None
                if s.mid and s.mid.status != Mark.Status.PRESENT:
                    s.note = s.mid.get_status_display()
                s.score = q2(pct) if pct is not None else None
            else:
                s.score = _annual_score(scheme, s, tests_by_subject[subject.id], marks, e.student_id)
            if s.score is None:
                complete = False
            else:
                s.grade = grade_for(scheme, s.score)
                s.passed = s.score >= scheme.pass_percent
                if not s.passed:
                    r.failed_subjects.append(subject)
            r.subjects.append(s)
        r.complete = complete
        if complete:
            r.maximum = HUNDRED * len(subjects)
            r.obtained = q2(sum(s.score for s in r.subjects))
            r.percent = q2(r.obtained * HUNDRED / r.maximum)
            r.grade = grade_for(scheme, r.percent)
        results.append(r)

    _assign_positions(results, scheme)
    return {"scheme": scheme, "results": results, "subjects": subjects, "mid_exam": mid_exam, "final_exam": final_exam}


def _annual_score(scheme, s, test_papers, marks, student_id):
    """Weighted score out of 100, or None if the result is not yet complete."""
    if s.final_paper is None:
        return None
    final_pct = _pct(s.final, s.final_paper)
    if final_pct is None:
        if s.final is not None and s.final.status != Mark.Status.PRESENT:
            s.note = s.final.get_status_display()
        return None  # no annual result without the Final

    weights = {"final": Decimal(scheme.final_weight)}
    parts = {"final": final_pct}

    if scheme.mid_weight:
        mid_pct = _pct(s.mid, s.mid_paper) if s.mid_paper else None
        excused = s.mid is not None and s.mid.status == Mark.Status.EXCUSED
        no_mid_exam = s.mid_paper is None
        if mid_pct is not None:
            weights["mid"], parts["mid"] = Decimal(scheme.mid_weight), mid_pct
        elif no_mid_exam or (excused and scheme.absent_mid_rule == GradingScheme.AbsentMid.FINAL_ONLY):
            weights["final"] += Decimal(scheme.mid_weight)  # Final carries the Mid-Term's share
            s.note = s.note or ("Mid-Term excused" if excused else "")
        else:
            weights["mid"], parts["mid"] = Decimal(scheme.mid_weight), Decimal(0)

    if scheme.test_weight:
        pcts = [p for p in (_pct(marks.get((tp.id, student_id)), tp) for tp in test_papers) if p is not None]
        if pcts:
            weights["test"], parts["test"] = Decimal(scheme.test_weight), sum(pcts) / len(pcts)
            s.test_percent = q2(parts["test"])
        else:
            weights["final"] += Decimal(scheme.test_weight)

    total_weight = sum(weights.values())
    return q2(sum(parts[k] * weights[k] for k in parts) / total_weight)


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
