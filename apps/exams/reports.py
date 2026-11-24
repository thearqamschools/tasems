"""Result reports (R15-10, project lead 24 Nov 2026): how a class / section did in an exam — pass at 33%, positions
(1st, 2nd, 3rd; equal percentages share a position), subject averages — and one student's progress across the exams.
Each exam stands alone (R14-4)."""

from decimal import Decimal

from apps.academics.models import Section

from . import grid
from .models import Exam, Mark, Paper

PASS_PERCENT = Decimal("33")  # lead, 24 Nov 2026
TWO = Decimal("0.01")


def _pct(part, whole):
    return (Decimal(part) * 100 / whole).quantize(TWO) if whole else None


def _avg(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values)).quantize(TWO) if values else None


def section_result(exam, section):
    data = grid.table(exam, section)
    papers = data["papers"]
    students = []
    for row in data["rows"]:
        marks = row["marks"]
        sat = any(m is not None for m in marks.values())
        obtained, total, percent = grid.student_totals(papers, marks)
        students.append(
            {
                "enrolment": row["enrolment"],
                "section": section,
                "marks": marks,
                "sat": sat,
                "obtained": obtained,
                "total": total,
                "percent": percent,
                "passed": percent is not None and percent >= PASS_PERCENT,
            }
        )
    return papers, students


def rank(students):
    """Positions by percentage, highest first; equal percentages share a position (1, 1, 3)."""
    ranked = sorted([s for s in students if s["percent"] is not None], key=lambda s: -s["percent"])
    position, last = 0, None
    for i, s in enumerate(ranked, start=1):
        if s["percent"] != last:
            position, last = i, s["percent"]
        s["position"] = position
    for s in students:
        s.setdefault("position", None)
    return ranked + [s for s in students if s["percent"] is None]


def summary(students):
    done = [s for s in students if s["percent"] is not None]
    passed = [s for s in done if s["passed"]]
    return {
        "students": len(students),
        "sat": sum(1 for s in students if s["sat"]),
        "complete": len(done),
        "passed": len(passed),
        "failed": len(done) - len(passed),
        "pass_rate": _pct(len(passed), len(done)) if done else None,
        "average": _avg([s["percent"] for s in done]),
        "highest": max((s["percent"] for s in done), default=None),
        "lowest": min((s["percent"] for s in done), default=None),
    }


def subject_rows(papers_by_section, students):
    """One row per subject: total, average % of those who sat it, highest marks, how many passed it."""
    by_subject = {}
    for s in students:
        for p in papers_by_section[s["section"].id]:
            m = s["marks"].get(p.id)
            entry = by_subject.setdefault(p.subject, {"total": p.total_marks, "pcts": [], "best": None, "passed": 0})
            if m is None:
                continue
            got = m.obtained if m.status == Mark.Status.PRESENT else Decimal("0")
            pct = _pct(got, p.total_marks)
            entry["pcts"].append(pct)
            entry["best"] = got if entry["best"] is None else max(entry["best"], got)
            if pct >= PASS_PERCENT:
                entry["passed"] += 1
    return [
        {
            "subject": subject,
            "total": e["total"],
            "average": _avg(e["pcts"]),
            "highest": e["best"],
            "sat": len(e["pcts"]),
            "passed": e["passed"],
        }  # fmt: skip
        for subject, e in sorted(by_subject.items(), key=lambda x: x[0].name)
    ]


def class_result(exam, sections):
    """Every section of the class (or the one section): students ranked together, per section and per subject."""
    papers_by_section, students, per_section = {}, [], []
    for section in sections:
        papers, rows = section_result(exam, section)
        papers_by_section[section.id] = papers
        students.extend(rows)
        per_section.append({"section": section, **summary(rows)})
    ranked = rank(students)
    return {
        "summary": summary(students),
        "students": ranked,
        "sections": per_section,
        "subjects": subject_rows(papers_by_section, students),
    }


def overview(exam, branch, session):
    """No class chosen: one line per class."""
    rows = []
    sections = (
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
    )
    by_class = {}
    for s in sections:
        by_class.setdefault(s.class_level, []).append(s)
    everyone = []
    for level, secs in by_class.items():
        students = []
        for s in secs:
            students.extend(section_result(exam, s)[1])
        everyone.extend(students)
        rows.append({"level": level, "sections": len(secs), **summary(students)})
    # R16-5: the whole school's result for the exam, at the end
    school = {"sections": sum(r["sections"] for r in rows), **summary(everyone)}
    return rows, school


def student_progress(student, session=None):
    """One student's every exam, subject by subject: {"exams": [...], "subjects": [(subject, [cell per exam])],
    "totals": [...]} — the exams of the session in order (or every session)."""
    marks = list(Mark.objects.filter(student=student).select_related("paper__exam__session", "paper__subject"))
    exams = sorted(
        {m.paper.exam for m in marks if session is None or m.paper.exam.session_id == session.id},
        key=lambda e: (e.session.starts_on, Exam.KIND_ORDER.get(e.kind, 9)),
    )
    by_exam = {e.id: {} for e in exams}
    for m in marks:
        if m.paper.exam_id in by_exam:
            by_exam[m.paper.exam_id][m.paper_id] = m
    subjects = {}
    totals = []
    previous = None
    for e in exams:
        papers = list(Paper.objects.filter(exam=e, pk__in=by_exam[e.id]).select_related("subject"))
        obtained, total, percent = grid.student_totals(papers, by_exam[e.id])
        change = (percent - previous).quantize(TWO) if percent is not None and previous is not None else None
        totals.append({"exam": e, "obtained": obtained, "total": total, "percent": percent, "change": change,
                       "passed": percent is not None and percent >= PASS_PERCENT})  # fmt: skip
        previous = percent if percent is not None else previous
        for p in papers:
            subjects.setdefault(p.subject, {})[e.id] = (p, by_exam[e.id][p.id])
    subject_rows_ = [
        (subject, [cells.get(e.id) for e in exams])
        for subject, cells in sorted(subjects.items(), key=lambda x: x[0].name)
    ]
    return {"exams": exams, "subjects": subject_rows_, "totals": totals}


def ordinal(n):
    if n is None:
        return ""
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")
