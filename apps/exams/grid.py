"""One exam, one section, on one table (R14-7, project lead 24 Nov 2026): students down the side, the subjects across
the top, and the Attentive / Punctual / Neatness / Participation ratings. The same table comes out as an Excel or a
printed sheet to fill in by hand, and an Excel comes back in. Each exam stands alone (R14-4): the card shows only that
exam's papers."""

import io
from decimal import Decimal

from django.db import transaction

from . import services
from .models import Exam, ExamRating, Mark, Paper

LEVEL_LETTERS = {"excellent": "E", "good": "G", "fair": "F"}
LETTER_LEVELS = {"E": "excellent", "G": "good", "F": "fair"}


def papers_for(exam, section):
    """The exam's papers of the class in the class's subject order (R19-6)."""
    from apps.academics.order import sort_key, subject_order

    papers = list(Paper.objects.filter(exam=exam, class_level=section.class_level).select_related("subject"))
    return sorted(papers, key=sort_key(subject_order(section.class_level)))


def code_key(code):
    """Computer codes in number order (2, 10, 100); other codes after them in text order (R19-3)."""
    text = str(code or "").strip()
    return (0, int(text), "") if text.isdigit() else (1, 0, text.lower())


def table(exam, section):
    """{"papers": [...], "rows": [{"enrolment", "marks": {paper_id: Mark}, "rating": ExamRating|None}], "total": n}"""
    papers = papers_for(exam, section)
    entries = services.roster(section)
    ids = [e.student_id for e in entries]
    marks = {}
    for m in Mark.objects.filter(paper__in=papers, student_id__in=ids):
        marks.setdefault(m.student_id, {})[m.paper_id] = m
    ratings = {r.student_id: r for r in ExamRating.objects.filter(exam=exam, student_id__in=ids)}
    entries = sorted(entries, key=lambda e: code_key(e.student.admission_no))  # Comp. Code order, smallest first
    rows = [
        {"enrolment": e, "marks": marks.get(e.student_id, {}), "rating": ratings.get(e.student_id)} for e in entries
    ]
    return {"papers": papers, "rows": rows, "total": sum(p.total_marks for p in papers)}


def cell_text(mark):
    if mark is None:
        return ""
    if mark.status != Mark.Status.PRESENT:
        return "A"
    value = mark.obtained
    return str(int(value)) if value == value.to_integral_value() else str(value.normalize())


def parse_cell(raw, total):
    """ "" → None (not entered), "A" → absent, else marks (whole or half) within the total. ValueError otherwise."""
    text = (raw or "").strip()
    if text.upper() in ("A", "ABS", "ABSENT"):
        return (Mark.Status.ABSENT, None)
    value = services.parse_marks(text, total)
    return None if value is None else (Mark.Status.PRESENT, value)


def read_form(post, papers, rows):
    """→ (marks {paper_id: {student_id: (status, value)}}, ratings {student_id: {aspect: level}}, values, errors)."""
    marks, ratings, values, errors = {p.id: {} for p in papers}, {}, {}, {}
    for row in rows:
        sid = row["enrolment"].student_id
        for p in papers:
            raw = post.get(f"m_{sid}_{p.id}", "")
            values[(sid, p.id)] = raw
            try:
                parsed = parse_cell(raw, p.total_marks)
            except ValueError as exc:
                errors[(sid, p.id)] = str(exc)
                continue
            if parsed is not None:
                marks[p.id][sid] = parsed
        ratings[sid] = {
            aspect: post.get(f"r_{sid}_{aspect}") if post.get(f"r_{sid}_{aspect}") in LEVEL_LETTERS else "good"
            for aspect, _label in ExamRating.ASPECTS
        }
    return marks, ratings, values, errors


@transaction.atomic
def save(exam, section, papers, marks, ratings, user):
    saved = 0
    for p in papers:
        if marks.get(p.id):
            saved += services.save_marks(p, section, marks[p.id], user)
    existing = {r.student_id: r for r in ExamRating.objects.filter(exam=exam, student_id__in=ratings)}
    for sid, levels in ratings.items():
        r = existing.get(sid) or ExamRating(branch_id=section.branch_id, student_id=sid, exam=exam, section=section)
        changed = r.pk is None or any(getattr(r, k) != v for k, v in levels.items())
        if changed:
            for k, v in levels.items():
                setattr(r, k, v)
            r.section, r.entered_by = section, user
            r.save()
    return saved


def student_totals(papers, marks_by_paper):
    """(obtained, total, percent or None). Absent counts as 0; a paper not entered yet leaves the result open."""
    total = sum(p.total_marks for p in papers)
    obtained = Decimal("0")
    complete = True
    for p in papers:
        m = marks_by_paper.get(p.id)
        if m is None:
            complete = False
        elif m.status == Mark.Status.PRESENT:
            obtained += m.obtained
    percent = (obtained * 100 / total).quantize(Decimal("0.01")) if total and complete else None
    return obtained, total, percent


# --- Excel out and in ---------------------------------------------------------------------------------------------

KEY_ROW = 3  # hidden row with what each column is


def workbook(exam, section, data):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Marks"
    ws.append([f"{exam.name} — {section} — The Arqam Schools"])
    ws.append(
        ["Comp. Code", "Name"]
        + [f"{p.subject.short} ({p.total_marks})" for p in data["papers"]]
        + [str(label) for _a, label in ExamRating.ASPECTS]
    )
    ws.append(["student", ""] + [f"paper:{p.id}" for p in data["papers"]] + [a for a, _l in ExamRating.ASPECTS])
    ws.row_dimensions[KEY_ROW].hidden = True
    for row in data["rows"]:
        e, r = row["enrolment"], row["rating"]
        ws.append(
            [e.student.admission_no, e.student.full_name]
            + [cell_text(row["marks"].get(p.id)) for p in data["papers"]]
            + [LEVEL_LETTERS[getattr(r, a)] if r else "G" for a, _l in ExamRating.ASPECTS]
        )
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E3EFEB")
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    first_rating = 3 + len(data["papers"])
    if data["rows"]:
        from openpyxl.utils import get_column_letter

        dv = DataValidation(type="list", formula1='"E,G,F"', allow_blank=True)
        ws.add_data_validation(dv)
        last = KEY_ROW + len(data["rows"])
        dv.add(f"{get_column_letter(first_rating)}{KEY_ROW + 1}:{get_column_letter(first_rating + 3)}{last}")
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 26
    ws.freeze_panes = "C4"
    notes = wb.create_sheet("How to fill")
    for line in (
        "Type the marks under each subject (whole or half marks, not more than the total in brackets).",
        "A = absent. Leave a cell empty if the marks are not ready yet.",
        "Attentive, Punctual, Neatness, Participation: E = Excellent, G = Good, F = Fair.",
        "Do not change the Comp. Code column, the headings or the order of the columns.",
        "Then: TASEMS → Exams & Results → the exam → the section → Import Excel; check and press Save.",
    ):
        notes.append([line])
    notes.column_dimensions["A"].width = 110
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def read_workbook(file, papers, rows):
    """The Excel back → a dict like a submitted form ({"m_<student>_<paper>": text, "r_<student>_<aspect>": letter})
    and a list of problems. Rows are matched by Comp. Code (computer code)."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(file, data_only=True, read_only=True)
    except Exception:  # noqa: BLE001 - any unreadable file
        return None, ["The file could not be read as an Excel (.xlsx) file."]
    ws = wb["Marks"] if "Marks" in wb.sheetnames else wb.worksheets[0]
    all_rows = list(ws.iter_rows(values_only=True))
    if len(all_rows) < KEY_ROW:
        return None, ["This is not TASEMS's marks sheet (download it from the section's marks page)."]
    key = [str(c or "") for c in all_rows[KEY_ROW - 1]]
    paper_ids = {p.id for p in papers}
    columns = {}
    for i, k in enumerate(key):
        if k.startswith("paper:") and k[6:].isdigit() and int(k[6:]) in paper_ids:
            columns[i] = ("paper", int(k[6:]))
        elif k in dict(ExamRating.ASPECTS):
            columns[i] = ("rating", k)
    if not columns:
        return None, ["This sheet is for another exam or class (download it from this section's marks page)."]
    by_code = {str(r["enrolment"].student.admission_no).strip().upper(): r["enrolment"].student_id for r in rows}
    form, problems = {}, []
    for n, values in enumerate(all_rows[KEY_ROW:], start=KEY_ROW + 1):
        if not values or not any(v not in (None, "") for v in values):
            continue
        code = str(values[0] or "").strip().upper()
        sid = by_code.get(code)
        if sid is None:
            problems.append(f"Row {n}: Comp. Code {code or '(empty)'} is not a student of this section; left out.")
            continue
        for i, (kind, ref) in columns.items():
            value = values[i] if i < len(values) else None
            text = (
                ""
                if value is None
                else (str(int(value)) if isinstance(value, float) and value.is_integer() else str(value))
            )
            if kind == "paper":
                form[f"m_{sid}_{ref}"] = text.strip()
            else:
                letter = text.strip().upper()[:1]
                form[f"r_{sid}_{ref}"] = LETTER_LEVELS.get(letter, "good")
    return form, problems


def exams_in_order(queryset):
    return sorted(queryset, key=lambda e: (e.session.starts_on if e.session_id else None, e.order))


def progress(student):
    """Every exam the student sat, every year: (exam, obtained, total, percent) — R14-10 (9)."""
    out = []
    marks = Mark.objects.filter(student=student).select_related("paper__exam__session", "paper")
    by_exam = {}
    for m in marks:
        by_exam.setdefault(m.paper.exam, {})[m.paper_id] = m
    for exam, by_paper in by_exam.items():
        papers = list(Paper.objects.filter(exam=exam, pk__in=by_paper))
        obtained, total, percent = student_totals(papers, by_paper)
        out.append({"exam": exam, "obtained": obtained, "total": total, "percent": percent})
    return sorted(out, key=lambda x: (x["exam"].session.starts_on, Exam.KIND_ORDER.get(x["exam"].kind, 9)))
