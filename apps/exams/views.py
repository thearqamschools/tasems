"""Examination screens: exams for the branch, marks entry, section results, result cards."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.academics.models import Section
from apps.core.branch import current_branch
from apps.diary.models import DiaryLayout
from apps.organisation.models import AcademicSession

from . import results as R
from . import services
from .models import Exam, GradingComponent, GradingScheme, Mark, Paper, Rating, ResultRemark


def _branch(request):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(services.VIEW_PERM, branch.id):
        raise PermissionDenied
    return branch


def _exams(branch, session):
    return Exam.objects.filter(session=session).filter(Q(branch__isnull=True) | Q(branch=branch))


@login_required
def index(request):
    branch = _branch(request)
    session = AcademicSession.objects.filter(is_current=True).first()
    exams = list(_exams(branch, session).prefetch_related("papers")) if session else []
    sections = (
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
        if session
        else []
    )
    mine = [s for s in sections if s.class_teacher_id == request.user.id]
    return render(request, "exams/index.html", {"exams": exams, "sections": sections, "mine": mine, "session": session})


def _section(request, branch, section_id):
    section = (
        Section.objects.filter(pk=section_id, branch=branch).select_related("class_level", "session", "branch").first()
    )
    if section is None:
        raise Http404
    return section


@login_required
def section_exam(request, exam_id, section_id):
    """Papers of one exam for one section, with how many marks are entered."""
    branch = _branch(request)
    section = _section(request, branch, section_id)
    exam = _exams(branch, section.session).filter(pk=exam_id).first()
    if exam is None:
        raise Http404
    papers = list(exam.papers.filter(class_level=section.class_level).select_related("subject"))
    count = len(services.roster(section))
    entered = {p.id: Mark.objects.filter(paper=p, section=section).count() for p in papers}
    return render(
        request,
        "exams/section_exam.html",
        {
            "exam": exam,
            "section": section,
            "papers": [(p, entered[p.id]) for p in papers],
            "students": count,
            "can_enter": services.can_enter(request.user, section, exam),
            "can_remark": services.can_write_remarks(request.user, section),
        },
    )


@login_required
def enter_marks(request, paper_id, section_id):
    branch = _branch(request)
    section = _section(request, branch, section_id)
    paper = (
        Paper.objects.filter(pk=paper_id, class_level=section.class_level)
        .filter(Q(exam__branch__isnull=True) | Q(exam__branch=branch))
        .select_related("exam", "subject")
        .first()
    )
    if paper is None:
        raise Http404
    if not services.can_enter(request.user, section, paper.exam):
        raise PermissionDenied
    entries = services.roster(section)
    existing = {
        m.student_id: m for m in Mark.objects.filter(paper=paper, student_id__in=[e.student_id for e in entries])
    }
    errors = {}
    if request.method == "POST":
        data = {}
        for e in entries:
            status = request.POST.get(f"st{e.student_id}", Mark.Status.PRESENT)
            if status not in Mark.Status.values:
                status = Mark.Status.PRESENT
            raw = request.POST.get(f"m{e.student_id}", "")
            try:
                value = services.parse_marks(raw, paper.total_marks) if status == Mark.Status.PRESENT else None
            except ValueError as exc:
                errors[e.student_id] = (raw, str(exc))
                continue
            data[e.student_id] = (status, value)
        if not errors:
            saved = services.save_marks(paper, section, data, request.user)
            messages.success(request, _("Marks saved for %(n)s students.") % {"n": saved})
            return redirect("exams:section_exam", exam_id=paper.exam_id, section_id=section.id)
        messages.error(request, _("Some marks need correcting. Nothing was saved."))

    rows = []
    for e in entries:
        m = existing.get(e.student_id)
        raw, error = errors.get(e.student_id, (None, ""))
        rows.append(
            {
                "enrolment": e,
                "value": raw if raw is not None else (R.plain(m.obtained) if m and m.obtained is not None else ""),
                "status": request.POST.get(f"st{e.student_id}") if errors else (m.status if m else "present"),
                "error": error,
            }
        )
    return render(
        request,
        "exams/enter_marks.html",
        {"paper": paper, "section": section, "rows": rows, "statuses": Mark.Status.choices},
    )


@login_required
def section_results(request, section_id):
    branch = _branch(request)
    section = _section(request, branch, section_id)
    card = "mid" if request.GET.get("card") == "mid" else "annual"
    data = R.section_results(section, card)
    return render(
        request,
        "exams/section_results.html",
        {"section": section, "card": card, "can_rate": services.can_rate(request.user, section), **data},
    )


def _card_context(section, card, results_data, for_file):
    from django.conf import settings

    exam = results_data["final_exam"] if card == "annual" else results_data["mid_exam"]
    remarks = {}
    if exam:
        remarks = {
            r.student_id: r
            for r in ResultRemark.objects.filter(
                exam=exam, student_id__in=[x.student.id for x in results_data["results"]]
            )
        }
    from apps.people.models import StudentGuardian

    guardians = {
        link.student_id: link.guardian
        for link in StudentGuardian.objects.filter(
            student_id__in=[x.student.id for x in results_data["results"]], is_primary_contact=True
        ).select_related("guardian")
    }
    for r in results_data["results"]:
        r.remark = remarks.get(r.student.id)
        r.guardian = guardians.get(r.student.id)
    scheme = results_data["scheme"]
    bands = sorted(scheme.bands, key=lambda b: b["min"], reverse=True) if scheme else []
    band_rows = [(b["grade"], b["min"], None if i == 0 else bands[i - 1]["min"] - 1) for i, b in enumerate(bands)]
    return {
        **results_data,
        "band_rows": band_rows,
        "section": section,
        "card": card,
        "exam": exam,
        "remarks": remarks,
        "layout": DiaryLayout.current(),
        "font_base": f"file://{settings.BASE_DIR}/static/fonts/" if for_file else f"{settings.STATIC_URL}fonts/",
        "media_base": f"file://{settings.MEDIA_ROOT}/" if for_file else settings.MEDIA_URL,
    }


@login_required
def result_card(request, section_id, student_id=None):
    """One student's card, or every card of the section (one page each). ?format=pdf for PDF."""
    branch = _branch(request)
    section = _section(request, branch, section_id)
    card = "mid" if request.GET.get("card") == "mid" else "annual"
    data = R.section_results(section, card)
    if student_id is not None:
        data["results"] = [r for r in data["results"] if r.student.id == student_id]
        if not data["results"]:
            raise Http404
    as_pdf = request.GET.get("format") == "pdf"
    context = _card_context(section, card, data, for_file=as_pdf)
    if not as_pdf:
        return render(request, "exams/card_page.html", context)
    from weasyprint import HTML

    html = render_to_string("exams/card_document.html", context)
    pdf = HTML(string=html).write_pdf()
    name = f"Result-{card}-{str(section).replace(' ', '')}"
    if student_id is not None:
        name += f"-{data['results'][0].student.admission_no}"
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    return response


@login_required
def remarks(request, section_id, exam_id):
    branch = _branch(request)
    section = _section(request, branch, section_id)
    exam = _exams(branch, section.session).filter(pk=exam_id).first()
    if exam is None or not services.can_write_remarks(request.user, section):
        raise PermissionDenied
    is_principal = request.user.has_branch_perm(services.CHANGE_PERM, branch.id)
    entries = services.roster(section)
    existing = {
        r.student_id: r for r in ResultRemark.objects.filter(exam=exam, student_id__in=[e.student_id for e in entries])
    }
    if request.method == "POST":
        for e in entries:
            r = existing.get(e.student_id) or ResultRemark(branch=branch, student=e.student, exam=exam)
            r.teacher_remarks = request.POST.get(f"t{e.student_id}", r.teacher_remarks).strip()
            if is_principal:
                r.principal_remarks = request.POST.get(f"p{e.student_id}", r.principal_remarks).strip()
            if r.pk or r.teacher_remarks or r.principal_remarks:
                r.save()
        messages.success(request, _("Remarks saved."))
        return redirect(f"/exams/section/{section.id}/results/?card={'mid' if exam.kind == 'mid' else 'annual'}")
    rows = [{"enrolment": e, "remark": existing.get(e.student_id)} for e in entries]
    return render(
        request, "exams/remarks.html", {"section": section, "exam": exam, "rows": rows, "is_principal": is_principal}
    )


@login_required
def ratings(request, section_id):
    """Teacher's marks for discipline, neatness, summer work and class work."""
    branch = _branch(request)
    section = _section(request, branch, section_id)
    if not services.can_rate(request.user, section):
        raise PermissionDenied
    scheme = GradingScheme.for_stage(section.class_level.stage)
    components = list(scheme.components.filter(source=GradingComponent.Source.RATING)) if scheme else []
    if not components:
        raise Http404
    component = next((c for c in components if c.code == request.GET.get("component")), components[0])
    subjects = [s for s, _o in _class_subjects(section)]
    subject = None
    if component.scope == GradingComponent.Scope.SUBJECT:
        subject = next(
            (s for s in subjects if str(s.id) == request.GET.get("subject")), subjects[0] if subjects else None
        )
        if subject is None:
            raise Http404
    entries = services.roster(section)
    existing = {
        r.student_id: r.value
        for r in Rating.objects.filter(
            student_id__in=[e.student_id for e in entries],
            session=section.session,
            component=component,
            subject=subject,
        )
    }
    errors = {}
    if request.method == "POST":
        values = {}
        for e in entries:
            raw = request.POST.get(f"r{e.student_id}", "")
            try:
                values[e.student_id] = services.parse_rating(raw, component.max_marks)
            except ValueError as exc:
                errors[e.student_id] = (raw, str(exc))
        if not errors:
            services.save_ratings(section, component, subject, values, request.user)
            messages.success(request, _("%(name)s saved.") % {"name": component.name})
            return redirect(request.get_full_path())
        messages.error(request, _("Some values need correcting. Nothing was saved."))
    rows = []
    for e in entries:
        raw, error = errors.get(e.student_id, (None, ""))
        value = existing.get(e.student_id)
        rows.append(
            {
                "enrolment": e,
                "value": raw if raw is not None else (R.plain(value) if value is not None else ""),
                "error": error,
            }
        )
    return render(
        request,
        "exams/ratings.html",
        {
            "section": section,
            "components": components,
            "component": component,
            "subjects": subjects,
            "subject": subject,
            "rows": rows,
        },
    )


def _class_subjects(section):
    from apps.diary.services import subjects_for

    return subjects_for(section)


# --- Date sheet, exam slips, award lists (M7) ------------------------------------------------


@login_required
def date_sheet(request, exam_id):
    from apps.academics.models import ClassLevel

    from . import documents

    branch = _branch(request)
    session = AcademicSession.objects.filter(is_current=True).first()
    exam = _exams(branch, session).filter(pk=exam_id).first() if session else None
    if exam is None:
        raise Http404
    can_edit = documents.can_edit_date_sheet(request.user, exam, branch)
    # The branch's classes; network exam setup sees every class of a network exam, since its dates apply to all.
    all_levels = (
        ClassLevel.objects.filter(pk__in=exam.papers.values("class_level"))
        if can_edit and not exam.branch_id
        else ClassLevel.objects.filter(sections__branch=branch, sections__session=session).distinct()
    )
    levels = all_levels
    level_id = request.GET.get("class", "")
    if level_id.isdigit():
        levels = levels.filter(pk=level_id)
    editing = can_edit and (request.GET.get("edit") == "1" or request.method == "POST")
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        errors = 0
        for p in exam.papers.filter(class_level__in=levels):
            values = {k: request.POST.get(f"{k}_{p.id}", "").strip() for k in ("date", "starts_at", "ends_at")}
            try:
                p.date = dt.date.fromisoformat(values["date"]) if values["date"] else None
                p.starts_at = dt.time.fromisoformat(values["starts_at"]) if values["starts_at"] else None
                p.ends_at = dt.time.fromisoformat(values["ends_at"]) if values["ends_at"] else None
            except ValueError:
                errors += 1
                continue
            p.save(update_fields=["date", "starts_at", "ends_at", "updated_at"])
        if errors:
            messages.warning(request, _("%(n)s papers had a date or time that could not be read.") % {"n": errors})
        else:
            messages.success(request, _("Date sheet saved."))
        return redirect(f"{reverse('exams:date_sheet', args=[exam.id])}?class={level_id}")
    return render(
        request,
        "exams/date_sheet.html",
        {
            "exam": exam,
            "branch": branch,
            "sheet": documents.date_sheet(exam, levels),
            "levels": all_levels,
            "level_id": level_id,
            "can_edit": can_edit,
            "editing": editing,
        },
    )


@login_required
def exam_slips(request, exam_id, section_id):
    from . import documents

    branch = _branch(request)
    section = _section(request, branch, section_id)
    exam = _exams(branch, section.session).filter(pk=exam_id).first()
    if exam is None:
        raise Http404
    enrolments = services.roster(section)
    student_id = request.GET.get("student", "")
    if student_id.isdigit():
        enrolments = [e for e in enrolments if e.student_id == int(student_id)]
    if not enrolments:
        raise Http404
    response = HttpResponse(documents.slips_pdf(exam, section, enrolments), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Exam slips {section} {exam.name}.pdf"'
    return response


@login_required
def award_list(request, paper_id, section_id):
    from apps.core import exports

    branch = _branch(request)
    section = _section(request, branch, section_id)
    paper = Paper.objects.filter(pk=paper_id, class_level=section.class_level).select_related("exam", "subject").first()
    if paper is None or not _exams(branch, section.session).filter(pk=paper.exam_id).exists():
        raise Http404
    marks = {m.student_id: m for m in Mark.objects.filter(paper=paper, section=section)}
    rows = [{"e": e, "mark": marks.get(e.student_id)} for e in services.roster(section)]
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Award list") + f" {section} {paper.subject.name}",
            [_("Roll no."), _("Admission no."), _("Name"), _("Father name"), _("Marks obtained"), _("Total marks")],
            (
                [
                    r["e"].roll_no,
                    r["e"].student.admission_no,
                    r["e"].student.full_name,
                    r["e"].student.father_name,
                    (r["mark"].obtained if r["mark"].status == Mark.Status.PRESENT else r["mark"].get_status_display())
                    if r["mark"]
                    else "",
                    paper.total_marks,
                ]
                for r in rows
            ),
            branch=branch,
        )
    return render(request, "exams/award_list.html", {"paper": paper, "section": section, "rows": rows})
