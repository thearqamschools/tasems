"""The year's four exams (Round 14, project lead 24 Nov 2026): set up the session's exams in one click, the papers
and total marks of each class (copied from an earlier exam), question papers kept on record, the date sheet as one
grid (PDF, no times), the marks of a whole section on one table (or Excel in and out), and black-and-white result
cards for every exam."""

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

from apps.academics.models import ClassLevel, Subject
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
        for subject in _subjects(exam):
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
        for s in _subjects(exam)
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


def _subjects(exam):
    """Every active subject; Summer Vacation Work only in the Mid-Term (R14-8), at the top."""
    subjects = list(Subject.objects.filter(is_active=True).order_by("name"))
    summer = [s for s in subjects if s.code == SUMMER_WORK]
    others = [s for s in subjects if s.code != SUMMER_WORK]
    return (summer + others) if exam.kind == Exam.Kind.MID else others


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
                return redirect(request.path)
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
                return redirect(request.path)
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
        },
    )


def _blank_sheet(request, exam, section, data):
    """The sheet to fill by hand (R14-7 (2)): the same columns as the Excel, opened to print."""
    headers = ["Code", "Roll", "Name"] + [f"{p.subject.name} ({p.total_marks})" for p in data["papers"]]
    headers += ["Attentive", "Punctual", "Neatness", "Participation"]
    rows = []
    for row in data["rows"]:
        e = row["enrolment"]
        line = [{"text": e.student.admission_no}, {"text": e.roll_no or ""}, {"text": e.student.full_name, "cls": "l"}]
        line += [{"text": grid.cell_text(row["marks"].get(p.id))} for p in data["papers"]]
        line += [{"text": ""} for _a in ExamRating.ASPECTS]
        rows.append(line)
    context = {
        "branch": section.branch,
        "title": exam.name.upper(),
        "subtitle": f"{section} · Marks sheet",
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
            "address": _address(section.branch),
            "logo": _grey_logo(),
            "font_base": f"file://{settings.BASE_DIR}/static/fonts/",
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


def _address(branch):
    lines = [x.strip() for x in (branch.address or "").splitlines() if x.strip()]
    if lines:
        return f"The Arqam Schools, {', '.join(lines)}"
    return "The Arqam Schools, Sanora Colony, Samanabad, Faisalabad"


def _grey_logo():
    """The official logo in grey for the black-and-white card (the lead's own card prints it in black); the shape
    is unchanged. A logo uploaded in Setup is used when there is one."""
    import base64

    from PIL import Image

    layout = DiaryLayout.current()
    path = Path(layout.left_logo.path) if layout and getattr(layout, "left_logo", None) else None
    if path is None or not path.exists():
        path = Path(settings.BASE_DIR) / "static" / "img" / "arqam-logo-512.png"
    image = Image.open(path).convert("LA")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


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
