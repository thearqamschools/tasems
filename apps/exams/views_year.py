"""The year's four exams (Round 14, project lead 24 Nov 2026): set up the session's exams in one click, the papers
and total marks of each class (copied from an earlier exam), question papers kept on record, the date sheet as one
grid (PDF, no times), the marks of a whole section on one table (or Excel in and out), and black-and-white result
cards for every exam."""

import datetime as dt
import io
import zipfile
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import ClassLevel, Section, Subject
from apps.core import paths
from apps.diary.models import DiaryLayout
from apps.organisation.models import AcademicSession

from . import documents, grid, services
from .models import Exam, ExamRating, Paper
from .views import _branch, _exams, _section

SUMMER_WORK = "summer-vacation-work"
QUESTION_PAPER_TYPES = (".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx")


def _exam(request, branch, exam_id):
    session = AcademicSession.objects.filter(is_current=True).first()
    exam = (
        Exam.objects.filter(pk=exam_id)
        .filter(Q(branch__isnull=True) | Q(branch=branch))
        .select_related("session")
        .first()
    )
    if exam is None or session is None:
        raise Http404
    return exam


@login_required
@require_POST
def add_session_exams(request):
    """ "Add this session's exams" (R14-10 (1)): the four exams of the current session at once, network-wide for head
    office, else for this branch. Exams already there are kept."""
    branch = _branch(request)
    session = AcademicSession.objects.filter(is_current=True).first()
    if session is None:
        raise Http404
    network = documents.can_add_network_exams(request.user)
    if not network and not request.user.has_branch_perm("exams.add_exam", branch.id):
        raise PermissionDenied
    have = set(_exams(branch, session).values_list("kind", flat=True))
    made = 0
    for kind, label in Exam.Kind.choices:
        if kind in have:
            continue
        Exam.objects.create(
            session=session, kind=kind, name=f"{label} {session.name}", branch=None if network else branch
        )
        made += 1
    if made:
        messages.success(request, _("%(n)s exams added for session %(s)s.") % {"n": made, "s": session.name})
    else:
        messages.info(request, _("This session's four exams are already there."))
    return redirect("exams:index")


def _levels(exam, branch, user):
    """A network exam: every class (head office sets the papers for all); a branch's exam: its own classes."""
    if not exam.branch_id and documents.can_edit_date_sheet(user, exam, branch):
        return ClassLevel.objects.filter(is_active=True).order_by("sort_order")
    return (
        ClassLevel.objects.filter(sections__branch=branch, sections__session=exam.session)
        .distinct()
        .order_by("sort_order")
    )


@login_required
def papers(request, exam_id):
    """Papers of one exam, class by class: the subjects with their total marks (typed for every exam, R14-4), the
    question paper of each (R14-6), and "copy from" an earlier exam (R14-10 (2))."""
    branch = _branch(request)
    exam = _exam(request, branch, exam_id)
    can_edit = documents.can_edit_date_sheet(request.user, exam, branch)
    levels = list(_levels(exam, branch, request.user))
    if not levels:
        raise Http404
    level = next((lv for lv in levels if str(lv.id) == request.GET.get("class", "")), levels[0])
    here = f"{reverse('exams:papers', args=[exam.id])}?class={level.id}"
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        action = request.POST.get("action")
        if action == "dates":  # the exam's first and last day, once for every class (R16-3)
            try:
                first, last = request.POST.get("starts_on", "").strip(), request.POST.get("ends_on", "").strip()
                exam.starts_on = dt.date.fromisoformat(first) if first else None
                exam.ends_on = dt.date.fromisoformat(last) if last else None
                if exam.starts_on and exam.ends_on and exam.ends_on < exam.starts_on:
                    exam.starts_on, exam.ends_on = exam.ends_on, exam.starts_on
                exam.save(update_fields=["starts_on", "ends_on", "updated_at"])
                messages.success(request, _("Exam dates saved."))
            except ValueError:
                messages.error(request, _("The first or last day could not be read."))
            return redirect(here)
        if action == "copy":
            source = Exam.objects.filter(pk=request.POST.get("source")).first()
            if source is None or source.pk == exam.pk:
                messages.error(request, _("Choose the exam to copy from."))
                return redirect(here)
            have = set(exam.papers.values_list("class_level_id", "subject_id"))
            made = 0
            for p in source.papers.all():
                if (p.class_level_id, p.subject_id) in have:
                    continue
                if p.subject.code == SUMMER_WORK and exam.kind != Exam.Kind.MID:
                    continue
                Paper.objects.create(
                    exam=exam, class_level_id=p.class_level_id, subject_id=p.subject_id, total_marks=p.total_marks
                )
                made += 1
            messages.success(
                request,
                _("%(n)s papers copied from %(e)s. Change any total marks as needed.") % {"n": made, "e": source.name},
            )
            return redirect(here)
        existing = {p.subject_id: p for p in exam.papers.filter(class_level=level)}
        problems = []
        for subject in _subjects(exam, level):
            raw = request.POST.get(f"total_{subject.id}", "").strip()
            paper = existing.get(subject.id)
            upload = request.FILES.get(f"qp_{subject.id}")
            if raw == "":
                if paper is not None and not paper.marks.exists():
                    paper.delete()
                elif paper is not None:
                    problems.append(_("%(s)s has marks entered; it was kept.") % {"s": subject.name})
                continue
            if not raw.isdigit() or not 1 <= int(raw) <= 1000:
                problems.append(_("%(s)s: total marks must be a whole number.") % {"s": subject.name})
                continue
            if paper is None:
                paper = Paper(exam=exam, class_level=level, subject=subject)
            paper.total_marks = int(raw)
            day = request.POST.get(f"date_{subject.id}", "").strip()
            try:
                paper.date = dt.date.fromisoformat(day) if day else None
            except ValueError:
                problems.append(_("%(s)s: the date could not be read.") % {"s": subject.name})
            paper.starts_at = paper.ends_at = None
            if upload is not None:
                if not upload.name.lower().endswith(QUESTION_PAPER_TYPES) or upload.size > 20 * 1024 * 1024:
                    problems.append(
                        _("%(s)s: the question paper must be a PDF, photo or Word file under 20 MB.")
                        % {"s": subject.name}
                    )
                else:
                    paper.question_paper = upload
            paper.save()
        for p in problems:
            messages.warning(request, p)
        messages.success(request, _("Papers of %(c)s saved.") % {"c": level})
        return redirect(here)
    existing = {p.subject_id: p for p in exam.papers.filter(class_level=level)}
    rows = [
        {
            "subject": s,
            "paper": existing.get(s.id),
            "can_see": existing.get(s.id) is not None
            and documents.can_see_question_paper(request.user, existing[s.id], branch),
        }
        for s in _subjects(exam, level)
    ]
    if not can_edit:
        rows = [r for r in rows if r["paper"]]
    sources = [
        e
        for e in Exam.objects.filter(Q(branch__isnull=True) | Q(branch=branch))
        .exclude(pk=exam.pk)
        .select_related("session")
        if e.papers.exists()
    ]
    sources.sort(key=lambda e: (e.kind != exam.kind, -(e.session.starts_on.toordinal()), e.order))
    counts = {c: n for c, n in _paper_counts(exam)}
    return render(
        request,
        "exams/papers.html",
        {
            "exam": exam,
            "levels": [(lv, counts.get(lv.id, 0)) for lv in levels],
            "level": level,
            "rows": rows,
            "can_edit": can_edit,
            "sources": sources,
        },
    )


def _paper_counts(exam):
    from django.db.models import Count

    return exam.papers.values_list("class_level_id").annotate(n=Count("id"))


def _subjects(exam, level):
    """The class's subjects from Setup → Classes & subjects (R15-3; every active subject while none are set for the
    class); Summer Vacation Work only in the Mid-Term (R14-8), at the top. A subject with a paper already stays."""
    from apps.academics.models import CurriculumSubject

    mapped = [
        c.subject
        for c in CurriculumSubject.objects.filter(class_level=level, subject__is_active=True)
        .select_related("subject")
        .order_by("sort_order", "subject__name")
    ]
    subjects = mapped or list(Subject.objects.filter(is_active=True).order_by("name"))
    with_paper = set(exam.papers.filter(class_level=level).values_list("subject_id", flat=True))
    extra = [s for s in Subject.objects.filter(pk__in=with_paper) if s not in subjects]
    others = [s for s in subjects + extra if s.code != SUMMER_WORK]
    if exam.kind == Exam.Kind.MID:
        summer = Subject.objects.filter(code=SUMMER_WORK).first()
        return ([summer] if summer else []) + others
    return others


@login_required
def question_paper(request, paper_id):
    branch = _branch(request)
    paper = Paper.objects.filter(pk=paper_id).select_related("exam").first()
    if (
        paper is None
        or not paper.question_paper
        or not _exams(branch, paper.exam.session).filter(pk=paper.exam_id).exists()
    ):
        raise Http404
    if not documents.can_see_question_paper(request.user, paper, branch):
        raise PermissionDenied
    name = f"{paper.exam.name} {paper.class_level} {paper.subject.name}{Path(paper.question_paper.name).suffix}"
    return FileResponse(paper.question_paper.open("rb"), filename=name)


@login_required
def date_sheet_pdf(request, exam_id):
    branch = _branch(request)
    exam = _exam(request, branch, exam_id)
    levels = _levels(exam, branch, request.user)
    response = HttpResponse(documents.date_sheet_pdf(exam, levels, branch), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Date sheet {exam.name}.pdf"'
    return response


# --- Marks of a whole section on one table ----------------------------------------------------------------------


def _form_rows(data, values=None, errors=None, ratings=None):
    """Rows for the template: each cell's text, error, and each rating's level."""
    values, errors = values or {}, errors or {}
    out = []
    for row in data["rows"]:
        sid = row["enrolment"].student_id
        cells = []
        for p in data["papers"]:
            text = values.get((sid, p.id), grid.cell_text(row["marks"].get(p.id)))
            cells.append({"paper": p, "text": text, "error": errors.get((sid, p.id), "")})
        r = row["rating"]
        levels = (ratings or {}).get(sid) or {a: getattr(r, a) if r else "good" for a, _l in ExamRating.ASPECTS}
        out.append(
            {"enrolment": row["enrolment"], "cells": cells, "levels": [(a, levels[a]) for a, _l in ExamRating.ASPECTS]}
        )
    return out


@login_required
def section_marks(request, exam_id, section_id):
    """Students down the side, subjects across (R14-7); Enter = next student, A = absent; ratings start as Good."""
    branch = _branch(request)
    section = _section(request, branch, section_id)
    exam = _exams(branch, section.session).filter(pk=exam_id).first()
    if exam is None:
        raise Http404
    data = grid.table(exam, section)
    # R18-5: in Comp. Code or Name order, so marks are typed in the order of the paper sheets
    order = request.GET.get("sort") or "code"
    if order == "-code":  # Comp. Code order (smallest first) is the default (R19-3)
        data["rows"].reverse()
    elif order in ("name", "-name"):
        data["rows"].sort(key=lambda r: r["enrolment"].student.full_name.lower(), reverse=order == "-name")
    can_enter = services.can_enter(request.user, section, exam)
    if request.GET.get("format") == "xlsx":
        response = HttpResponse(
            grid.workbook(exam, section, data),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="Marks {exam.name} {section}.xlsx"'
        return response
    if request.GET.get("print"):
        return _blank_sheet(request, exam, section, data)
    values = errors = ratings = None
    imported = False
    if request.method == "POST":
        if not can_enter:
            raise PermissionDenied
        if request.POST.get("action") == "import":
            form, problems = grid.read_workbook(request.FILES.get("file"), data["papers"], data["rows"])
            for p in problems[:20]:
                messages.warning(request, p)
            if form is None:
                return redirect(request.get_full_path())
            _m, ratings, values, errors = grid.read_form(form, data["papers"], data["rows"])
            imported = True
            if errors:
                messages.error(
                    request, _("Some marks in the Excel need correcting (shown in red). Nothing is saved yet.")
                )
            else:
                messages.info(request, _("The Excel's marks are shown below. Check them and press Save marks."))
        else:
            marks, ratings, values, errors = grid.read_form(request.POST, data["papers"], data["rows"])
            if errors:
                messages.error(request, _("Some marks need correcting (shown in red). Nothing was saved."))
            else:
                grid.save(exam, section, data["papers"], marks, ratings, request.user)
                messages.success(request, _("Marks and ratings saved for %(s)s.") % {"s": section})
                return redirect(request.get_full_path())
    return render(
        request,
        "exams/section_marks.html",
        {
            "exam": exam,
            "section": section,
            "papers": data["papers"],
            "total": data["total"],
            "rows": _form_rows(data, values, errors, ratings),
            "can_enter": can_enter,
            "imported": imported,
            "levels": ExamRating.Level.choices,
            "aspects": ExamRating.ASPECTS,
            "sort": order,
        },
    )


def _blank_sheet(request, exam, section, data):
    """The sheet to fill by hand (R14-7 (2)): the same columns as the Excel, opened to print; with the class teacher,
    the exam's total marks at the top, and Obtained and % to fill (R19-2, R19-4); short subject names (R19-5)."""
    total = data["total"]
    headers = ["Comp. Code", "Name"] + [f"{p.subject.short} ({p.total_marks})" for p in data["papers"]]
    headers += [f"Obtained ({total})", "%", "Attentive", "Punctual", "Neatness", "Participation"]
    rows = []
    for row in data["rows"]:
        e = row["enrolment"]
        line = [{"text": e.student.admission_no}, {"text": e.student.full_name, "cls": "l"}]
        line += [{"text": grid.cell_text(row["marks"].get(p.id))} for p in data["papers"]]
        obtained, _t, percent = grid.student_totals(data["papers"], row["marks"])
        done = percent is not None
        line += [{"text": f"{obtained.normalize():f}" if done else ""}, {"text": f"{percent:.2f}" if done else ""}]
        line += [{"text": ""} for _a in ExamRating.ASPECTS]
        rows.append(line)
    teacher = section.class_teacher_name or "—"
    context = {
        "branch": section.branch,
        "title": exam.name.upper(),
        "subtitle": f"{section} · Class teacher: {teacher} · Total marks: {total}",
        "landscape": len(data["papers"]) > 6,
        "key": ["A = Absent", "Ratings: E = Excellent, G = Good, F = Fair"],
        "sections": [{"headers": headers, "rows": rows}],
        "cell_pad": "2.6mm 1.2mm",
        "layout": DiaryLayout.current(),
        "font_base": f"{settings.STATIC_URL}fonts/",
        "media_base": settings.MEDIA_URL,
        "printed": timezone.localtime(),
        "auto_print": True,
    }
    return HttpResponse(render_to_string("hr/report_document.html", context))


# --- Result cards (R14-9): black and white, like the school's own card ------------------------------------------


@login_required
def cards(request, exam_id, section_id):
    from weasyprint import HTML

    branch = _branch(request)
    section = _section(request, branch, section_id)
    exam = _exams(branch, section.session).filter(pk=exam_id).first()
    if exam is None:
        raise Http404
    data = grid.table(exam, section)
    student_id = request.GET.get("student", "")
    rows = [r for r in data["rows"] if not student_id or str(r["enrolment"].student_id) == student_id]
    if not rows:
        raise Http404
    cards = []
    for row in rows:
        obtained, total, percent = grid.student_totals(data["papers"], row["marks"])
        r = row["rating"]
        cards.append(
            {
                "e": row["enrolment"],
                "lines": [(p, row["marks"].get(p.id)) for p in data["papers"]],
                "obtained": obtained,
                "total": total,
                "percent": percent,
                "ratings": [(label, getattr(r, a) if r else "good") for a, label in ExamRating.ASPECTS],
            }
        )
    html = render_to_string(
        "exams/exam_card_document.html",
        {
            "exam": exam,
            "section": section,
            "cards": cards,
            "address": documents.branch_address(section.branch),  # R16-8: the address only
            "banner": _banner(),
            # R17-6: many subjects → the gaps and rows tighten so the card stays on one page
            "gap": "6mm" if len(data["papers"]) <= 7 else "4.5mm" if len(data["papers"]) <= 10 else "3mm",
            "cell": "2.3mm" if len(data["papers"]) <= 7 else "1.7mm" if len(data["papers"]) <= 10 else "1.2mm",
            "font_base": paths.font_base(),
            "levels": ExamRating.Level.choices,
        },
    )
    pdf = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    name = f"Result {exam.name} {section}"
    if student_id:
        name += f" {rows[0]['enrolment'].student.admission_no}"
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    return response


def _banner():
    """The school's colour logo banner sent by the lead (R15-1), used exactly as sent."""
    return paths.banner()


@login_required
def marks_skill(request):
    """The Claude skill that reads a photo / scan of a hand-filled marks sheet into TASEMS's marks Excel
    (lead's choice for reading hand-written marks; TASEMS itself sends nothing anywhere, D-097)."""
    _branch(request)
    folder = Path(__file__).resolve().parent / "skill"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(folder / "SKILL.md", "tasems-marks-reader/SKILL.md")
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="tasems-marks-reader.zip"'
    return response


# --- Result reports (R15-10) --------------------------------------------------------------------------------------


def _fmt(value, suffix=""):
    return "—" if value is None else f"{value.normalize() if hasattr(value, 'normalize') else value}{suffix}"


def _pct_text(value):
    return "—" if value is None else f"{value:.2f}%"


@login_required
def report(request, exam_id):
    """How a class / section did in an exam: pass (33%), positions, subject averages; every class at a glance when no
    class is chosen. Print, PDF and Excel."""
    from apps.hr.views import _report as paper_report

    from . import reports

    branch = _branch(request)
    exam = _exam(request, branch, exam_id)
    session = exam.session
    sections = list(
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
    )
    classes = sorted({s.class_level for s in sections}, key=lambda c: c.sort_order)
    class_id, section_id = request.GET.get("class", ""), request.GET.get("section", "")
    chosen = [s for s in sections if str(s.class_level_id) == class_id] if class_id.isdigit() else []
    if section_id.isdigit():
        chosen = [s for s in chosen if str(s.id) == section_id]
    context = {"exam": exam, "classes": classes, "class_id": class_id, "section_id": section_id,
               "class_sections": [s for s in sections if str(s.class_level_id) == class_id],
               "pass_percent": reports.PASS_PERCENT}  # fmt: skip
    if chosen:
        result = reports.class_result(exam, chosen)
        for s in result["students"]:
            s["place"] = reports.ordinal(s["position"]) if s["position"] and s["position"] <= 3 else ""
        context["result"] = result
        scope = str(chosen[0]) if len(chosen) == 1 else str(chosen[0].class_level)
        context["scope"] = scope
    else:
        context["overview"], context["school"] = reports.overview(exam, branch, session)
        scope = "All classes"
    fmt = request.GET.get("format")
    if fmt in ("pdf", "xlsx") or request.GET.get("print"):
        paper = _report_paper(exam, branch, scope, context)
        if fmt == "xlsx":
            return _report_xlsx(paper, f"Result {exam.name} {scope}")
        return paper_report(request, paper, f"Result {exam.name} {scope}")
    return render(request, "exams/report.html", context)


def _report_paper(exam, branch, scope, context):
    """The report as headings and rows for the paper report (PDF / print / Excel)."""
    sections = []
    summary_items = []
    if "result" in context:
        r = context["result"]
        s = r["summary"]
        summary_items = [("Students", s["students"]), ("Passed", s["passed"]), ("Failed", s["failed"]),
                         ("Pass rate", _pct_text(s["pass_rate"])), ("Average", _pct_text(s["average"])),
                         ("Highest", _pct_text(s["highest"])), ("Lowest", _pct_text(s["lowest"]))]  # fmt: skip
        sections.append({
            "heading": "Students by percentage",
            "headers": ["Position", "Comp. Code", "Name", "Section", "Marks", "%", "Result"],
            "rows": [[{"text": x["place"], "cls": "warn" if x["place"] else ""},
                      {"text": x["enrolment"].student.admission_no},
                      {"text": x["enrolment"].student.full_name, "cls": "l"}, {"text": x["section"].name},
                      {"text": f"{_fmt(x['obtained'])} / {x['total']}"}, {"text": _pct_text(x["percent"])},
                      {"text": ("Pass" if x["passed"] else "Fail") if x["percent"] is not None else "Not complete",
                       "cls": "" if x["passed"] or x["percent"] is None else "bad"}] for x in r["students"]],
        })  # fmt: skip
        sections.append({
            "heading": "Subjects",
            "headers": ["Subject", "Total marks", "Sat", "Average %", "Highest marks", f"Passed ({PASS_TEXT})"],
            "rows": [[{"text": x["subject"].name, "cls": "l"}, {"text": x["total"]}, {"text": x["sat"]},
                      {"text": _pct_text(x["average"])}, {"text": _fmt(x["highest"])}, {"text": x["passed"]}]
                     for x in r["subjects"]],
        })  # fmt: skip
        if len(r["sections"]) > 1:
            sections.append({
                "heading": "Sections",
                "headers": ["Section", "Students", "Passed", "Pass rate", "Average", "Highest"],
                "rows": [[{"text": x["section"].name}, {"text": x["students"]}, {"text": x["passed"]},
                          {"text": _pct_text(x["pass_rate"])}, {"text": _pct_text(x["average"])},
                          {"text": _pct_text(x["highest"])}] for x in r["sections"]],
            })  # fmt: skip
    else:
        sections.append({
            "heading": "Classes",
            "headers": ["Class", "Sections", "Students", "Passed", "Failed", "Pass rate", "Average", "Highest"],
            "rows": [[{"text": str(x["level"]), "cls": "l"}, {"text": x["sections"]}, {"text": x["students"]},
                      {"text": x["passed"]}, {"text": x["failed"]}, {"text": _pct_text(x["pass_rate"])},
                      {"text": _pct_text(x["average"])}, {"text": _pct_text(x["highest"])}]
                     for x in context["overview"]]
            + [[{"text": "Whole school", "cls": "l"}, {"text": context["school"]["sections"]},
                {"text": context["school"]["students"]}, {"text": context["school"]["passed"]},
                {"text": context["school"]["failed"]}, {"text": _pct_text(context["school"]["pass_rate"])},
                {"text": _pct_text(context["school"]["average"])}, {"text": _pct_text(context["school"]["highest"])}]],
        })  # fmt: skip
    return {
        "branch": branch,
        "title": f"RESULT · {exam.get_kind_display().upper()}",
        "subtitle": f"{scope} · Session {exam.session.name}",
        "landscape": False,
        "summary": summary_items,
        "key": [f"Pass = {PASS_TEXT} or more of the exam's total marks", "Positions: 1st, 2nd, 3rd by percentage"],
        "sections": sections,
    }


PASS_TEXT = "33%"


def _report_xlsx(paper, filename):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Result"
    ws.append([paper["title"], paper["subtitle"]])
    if paper["summary"]:
        ws.append([])
        ws.append([k for k, _v in paper["summary"]])
        ws.append([v for _k, v in paper["summary"]])
    for sec in paper["sections"]:
        ws.append([])
        ws.append([sec["heading"]])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
        ws.append(sec["headers"])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
        for row in sec["rows"]:
            ws.append([c["text"] for c in row])
    ws.column_dimensions["C"].width = 26
    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


@login_required
def progress_report(request, student_id):
    """One student's progress (R15-10): every exam of the session — or every year with ?all=1 — subject by subject,
    the total, percentage, pass / fail and the change from the exam before. Print or PDF."""
    from apps.hr.views import _report as paper_report
    from apps.people.models import Student

    from . import reports

    branch = _branch(request)
    student = Student.objects.filter(pk=student_id, branch=branch).first()
    if student is None:
        raise Http404
    session = None if request.GET.get("all") else AcademicSession.objects.filter(is_current=True).first()
    data = reports.student_progress(student, session)
    if not data["exams"]:
        messages.info(request, _("No exam marks for this student yet."))
        return redirect("people:student_detail", pk=student.pk)
    headers = ["Subject"] + [f"{e.get_kind_display()} {e.session.name}" if not session else e.get_kind_display()
                             for e in data["exams"]]  # fmt: skip
    rows = []
    for subject, cells in data["subjects"]:
        line = [{"text": subject.short, "cls": "l"}]
        for cell in cells:
            if cell is None:
                line.append({"text": "–"})
            else:
                p, m = cell
                got = "Absent" if m.status != "present" else _fmt(m.obtained)
                line.append({"text": f"{got} / {p.total_marks}", "cls": "bad" if m.status != "present" else ""})
        rows.append(line)
    rows.append(
        [{"text": "Total", "cls": "l"}] + [{"text": f"{_fmt(t['obtained'])} / {t['total']}"} for t in data["totals"]]
    )
    rows.append([{"text": "Percentage", "cls": "l"}] + [{"text": _pct_text(t["percent"])} for t in data["totals"]])
    rows.append([{"text": "Result", "cls": "l"}] + [
        {"text": ("Pass" if t["passed"] else "Fail") if t["percent"] is not None else "—",
         "cls": "" if t["passed"] or t["percent"] is None else "bad"} for t in data["totals"]])  # fmt: skip
    rows.append([{"text": "Change from the exam before", "cls": "l"}] + [
        {"text": "—" if t["change"] is None else f"{t['change']:+.2f}%",
         "cls": "bad" if t["change"] and t["change"] < 0 else ""}
        for t in data["totals"]])  # fmt: skip
    from apps.people.services import current_enrolment

    enrolment = current_enrolment(student, AcademicSession.objects.filter(is_current=True).first())
    paper = {
        "branch": branch,
        "title": "PROGRESS REPORT",
        "subtitle": f"{student.full_name} · Comp. Code {student.admission_no}"
        + (f" · {enrolment.section}" if enrolment else "")
        + (f" · Session {session.name}" if session else " · All years"),
        "landscape": len(data["exams"]) > 5,
        "summary": [(f"{t['exam'].get_kind_display()}", _pct_text(t["percent"])) for t in data["totals"]][-7:],
        "key": [f"Pass = {PASS_TEXT} or more of the exam's total marks", "Each exam stands alone"],
        "sections": [{"headers": headers, "rows": rows}],
    }
    return paper_report(request, paper, f"Progress {student.admission_no}")
