"""Student register: list, view, add, edit and Excel import for the current branch."""

import secrets
import time
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Length
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.academics.models import ClassLevel, Section
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.fees.services import balance as fee_balance
from apps.organisation.models import AcademicSession

from . import certificates, idcards, importer
from . import promotion as promote
from .forms import CertificateForm, LeaveForm, StudentForm, section_order
from .models import Certificate, Enrolment, Student, StudentGuardian
from .services import current_enrolment

PAGE_SIZE = 50


def _branch_or_403(request, permission):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(permission, branch.id):
        raise PermissionDenied
    return branch


def _current_session():
    return AcademicSession.objects.filter(is_current=True).first()


def _get_student(request, pk, branch):
    student = Student.objects.for_user(request.user).filter(pk=pk, branch=branch).first()
    if student is None:
        raise Http404
    return student


@login_required
def student_list(request):
    branch = _branch_or_403(request, "people.view_student")
    session = _current_session()
    students = Student.objects.filter(branch=branch)

    status = request.GET.get("status", Student.Status.ACTIVE)
    if status in Student.Status.values:
        students = students.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        match = (
            Q(admission_no__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(father_name__icontains=q)
            | Q(full_name_ur__icontains=q)
        )
        if len(digits) >= 4:
            match |= Q(guardian_links__guardian__phone__contains=digits)
        students = students.filter(match).distinct()

    sections = Section.objects.filter(branch=branch, session=session) if session else Section.objects.none()
    section_names = sorted(set(sections.values_list("name", flat=True)), key=section_order)
    section_name = request.GET.get("section", "")
    level_id = request.GET.get("class", "")
    if session and level_id.isdigit():
        students = students.filter(enrolments__session=session, enrolments__section__class_level_id=level_id)
    if session and section_name:
        students = students.filter(enrolments__session=session, enrolments__section__name=section_name)

    enrolments = Enrolment.objects.filter(session=session).select_related("section__class_level") if session else []
    students = students.prefetch_related(
        Prefetch("enrolments", queryset=enrolments, to_attr="current_enrolments") if session else "enrolments",
        Prefetch(
            "guardian_links",
            queryset=StudentGuardian.objects.filter(is_primary_contact=True).select_related("guardian"),
            to_attr="primary_links",
        ),
    ).order_by(Length("admission_no"), "admission_no")

    page = Paginator(students, PAGE_SIZE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "people/student_list.html",
        {
            "page": page,
            "q": q,
            "status": status,
            "statuses": Student.Status.choices,
            "section_names": section_names,
            "levels": ClassLevel.objects.filter(is_active=True),
            "section_name": section_name,
            "level_id": level_id,
            "session": session,
            "querystring": params.urlencode(),
            "can_add": request.user.has_branch_perm("people.add_student", branch.id),
        },
    )


@login_required
def student_detail(request, pk):
    branch = _branch_or_403(request, "people.view_student")
    student = _get_student(request, pk, branch)
    can_edit = request.user.has_branch_perm("people.change_student", branch.id)
    history = []
    if can_edit:
        history = AuditEvent.objects.filter(model_label="people.Student", object_id=str(student.pk)).select_related(
            "actor"
        )[:20]
    return render(
        request,
        "people/student_detail.html",
        {
            "student": student,
            "links": student.guardian_links.select_related("guardian"),
            "enrolments": student.enrolments.select_related("session", "section__class_level", "section__campus"),
            "siblings": student.siblings().prefetch_related(
                Prefetch(
                    "enrolments",
                    queryset=Enrolment.objects.filter(session__is_current=True).select_related("section__class_level"),
                    to_attr="current_enrolments",
                )
            ),
            "can_edit": can_edit,
            "history": history,
            "certificates": student.certificates.select_related("issued_by"),
        },
    )


def _student_form(request, branch, student=None):
    session = _current_session()
    initial = {}
    if student is not None:
        enrolment = current_enrolment(student, session)
        if enrolment:
            initial.update(
                class_level=enrolment.section.class_level_id,
                section_name=enrolment.section.name,
                roll_no=enrolment.roll_no,
            )
    form = StudentForm(
        request.POST or None,
        request.FILES or None,
        instance=student,
        initial=initial,
        branch=branch,
        session=session,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save_all()
        messages.success(request, _("Saved %(name)s.") % {"name": saved.full_name})
        return redirect("people:student_detail", pk=saved.pk)
    return render(request, "people/student_form.html", {"form": form, "student": student, "session": session})


@login_required
def student_photo(request, pk):
    """Photos are private: only staff who may see this branch's students can open them."""
    branch = _branch_or_403(request, "people.view_student")
    student = _get_student(request, pk, branch)
    if not student.photo:
        raise Http404
    response = FileResponse(student.photo.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response


@login_required
def student_leave(request, pk):
    """Withdrawn / left, transferred out or graduated — with the fee balance shown first."""
    branch = _branch_or_403(request, "people.change_student")
    student = _get_student(request, pk, branch)
    owed = fee_balance(student)
    form = LeaveForm(request.POST or None, initial={"left_on": timezone.localdate(), "dues_cleared": owed <= 0})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        certificates.mark_left(student, d["status"], d["left_on"], request.user)
        messages.success(
            request, _("%(n)s is now marked as %(s)s.") % {"n": student.full_name, "s": student.get_status_display()}
        )
        if d["certificate"]:
            cert = certificates.issue(
                student,
                Certificate.Kind.LEAVING,
                request.user,
                conduct=d["conduct"],
                left_on=d["left_on"],
                reason=d["reason"],
                dues_cleared=d["dues_cleared"],
            )
            return redirect("people:certificate_pdf", pk=student.pk, cert_id=cert.pk)
        return redirect("people:student_detail", pk=student.pk)
    return render(request, "people/leave.html", {"student": student, "form": form, "owed": owed})


@login_required
def certificate_new(request, pk):
    """A character certificate (any time); a leaving certificate again only through "Leave school"."""
    branch = _branch_or_403(request, "people.change_student")
    student = _get_student(request, pk, branch)
    form = CertificateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cert = certificates.issue(student, Certificate.Kind.CHARACTER, request.user, **form.cleaned_data)
        return redirect("people:certificate_pdf", pk=student.pk, cert_id=cert.pk)
    return render(request, "people/certificate_form.html", {"student": student, "form": form})


@login_required
def certificate_pdf(request, pk, cert_id):
    branch = _branch_or_403(request, "people.view_student")
    student = _get_student(request, pk, branch)
    cert = Certificate.objects.filter(pk=cert_id, student=student).first()
    if cert is None:
        raise Http404
    response = HttpResponse(certificates.render_pdf(cert), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="{cert.get_kind_display()} {cert.reference or cert.number} - {student.full_name}.pdf"'
    )
    return response


PROMOTION_PERM = "people.add_enrolment"


@login_required
def promotion(request):
    """Next session, class by class: promote, keep in the same class, graduate (Class 10) or leave out."""
    branch = _branch_or_403(request, PROMOTION_PERM)
    current = _current_session()
    upcoming = promote.next_session(current)
    can_copy = request.user.has_branch_perm("academics.add_section", branch.id)
    if request.method == "POST" and request.POST.get("action") == "copy" and upcoming:
        if not can_copy:
            raise PermissionDenied
        made = promote.copy_sections(branch, current, upcoming)
        messages.success(request, _("%(n)s sections made for %(s)s.") % {"n": made, "s": upcoming})
        return redirect("people:promotion")
    sections = (
        list(
            Section.objects.filter(branch=branch, session=current, is_active=True)
            .select_related("class_level")
            .order_by("class_level__sort_order", "name")
        )
        if current
        else []
    )
    # Students of each section this year who already have a place next session.
    placed = (
        dict(
            Enrolment.objects.filter(branch=branch, session=current, student__enrolments__session=upcoming)
            .values("section")
            .annotate(n=Count("id"))
            .values_list("section", "n")
        )
        if upcoming
        else {}
    )
    active = (
        dict(
            Enrolment.objects.filter(branch=branch, session=current, student__status=Student.Status.ACTIVE)
            .values("section")
            .annotate(n=Count("id"))
            .values_list("section", "n")
        )
        if current
        else {}
    )
    graduated = (
        dict(
            Enrolment.objects.filter(branch=branch, session=current, student__status=Student.Status.GRADUATED)
            .values("section")
            .annotate(n=Count("id"))
            .values_list("section", "n")
        )
        if current
        else {}
    )
    rows = [
        {"section": sec, "students": active.get(sec.id, 0), "done": placed.get(sec.id, 0) + graduated.get(sec.id, 0)}
        for sec in sections
    ]
    return render(
        request,
        "people/promotion.html",
        {
            "current": current,
            "upcoming": upcoming,
            "rows": rows,
            "upcoming_sections": Section.objects.filter(branch=branch, session=upcoming).count() if upcoming else 0,
            "can_copy": can_copy,
        },
    )


@login_required
def promotion_section(request, section_id):
    branch = _branch_or_403(request, PROMOTION_PERM)
    current = _current_session()
    upcoming = promote.next_session(current)
    section = (
        Section.objects.filter(pk=section_id, branch=branch, session=current).select_related("class_level").first()
    )
    if section is None or upcoming is None:
        raise Http404
    enrolments = list(
        Enrolment.objects.filter(section=section, student__status=Student.Status.ACTIVE)
        .select_related("student")
        .order_by("student__first_name")
    )
    already = dict(
        Enrolment.objects.filter(session=upcoming, student__in=[e.student_id for e in enrolments]).values_list(
            "student_id", "section_id"
        )
    )
    next_level = promote.next_level(section.class_level)
    choices = list(
        Section.objects.filter(
            branch=branch, session=upcoming, class_level__in=[lv for lv in (next_level, section.class_level) if lv]
        )
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
    )
    by_id = {c.id: c for c in choices}
    default = promote.default_action(section.class_level)
    defaults = {a: promote.target_section(section, a, upcoming) for a in (promote.PROMOTE, promote.KEEP)}
    if request.method == "POST":
        decisions = {}
        for e in enrolments:
            action = request.POST.get(f"action-{e.student_id}", default)
            target = by_id.get(int(request.POST.get(f"to-{e.student_id}") or 0))
            if action in (promote.PROMOTE, promote.KEEP) and target is None:
                target = defaults[action]
            decisions[e.student_id] = (action, target)
        counts = promote.apply(section, upcoming, decisions, request.user)
        messages.success(
            request,
            _("%(p)s promoted, %(k)s kept in the same class, %(g)s graduated, %(s)s left out.")
            % {"p": counts["promote"], "k": counts["keep"], "g": counts["graduate"], "s": counts["skip"]},
        )
        return redirect("people:promotion")
    rows = []
    for e in enrolments:
        target_id = already.get(e.student_id)
        rows.append(
            {
                "enrolment": e,
                "done": target_id is not None,
                "action": default,
                "target": by_id.get(target_id) or defaults.get(default),
            }
        )
    return render(
        request,
        "people/promotion_section.html",
        {
            "section": section,
            "upcoming": upcoming,
            "next_level": next_level,
            "rows": rows,
            "choices": choices,
            "missing": default in defaults and defaults[default] is None,
            "actions": [
                (promote.PROMOTE, _("Promote")),
                (promote.KEEP, _("Keep in the same class")),
                (promote.GRADUATE, _("Graduate (passed out)")),
                (promote.SKIP, _("Leave out for now")),
            ],
        },
    )


@login_required
def id_cards(request):
    """ID cards for one student (?student=), or for a class/section of this session (?class=&section=)."""
    branch = _branch_or_403(request, "people.view_student")
    session = _current_session()
    enrolments = Enrolment.objects.filter(
        branch=branch, session=session, student__status=Student.Status.ACTIVE
    ).select_related("student", "section__class_level")
    student_id, level_id, section_name = (request.GET.get(k, "") for k in ("student", "class", "section"))
    if student_id.isdigit():
        student = _get_student(request, int(student_id), branch)
        enrolment = enrolments.filter(student=student).first()
        cards = [(student, enrolment.section if enrolment else None)]
    else:
        if level_id.isdigit():
            enrolments = enrolments.filter(section__class_level_id=level_id)
        if section_name:
            enrolments = enrolments.filter(section__name=section_name)
        enrolments = enrolments.order_by("section__class_level__sort_order", "section__name", "student__first_name")
        cards = [(e.student, e.section) for e in enrolments[:400]]
    if not cards:
        messages.error(request, _("No students to print ID cards for. Choose a class and section first."))
        return redirect("people:student_list")
    response = HttpResponse(idcards.render_pdf(branch, session, cards), content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="ID cards.pdf"'
    return response


@login_required
def student_create(request):
    branch = _branch_or_403(request, "people.add_student")
    return _student_form(request, branch)


@login_required
def student_edit(request, pk):
    branch = _branch_or_403(request, "people.change_student")
    return _student_form(request, branch, _get_student(request, pk, branch))


# ---------------------------------------------------------------- Excel import


def _import_dir():
    """Checked files wait here until imported. Files older than a day are removed."""
    path = Path(settings.MEDIA_ROOT) / "imports"
    path.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 24 * 3600
    for old in path.glob("*.xlsx"):
        if old.stat().st_mtime < cutoff:
            old.unlink(missing_ok=True)
    return path


@login_required
def import_template(request):
    _branch_or_403(request, "people.add_student")
    response = HttpResponse(
        importer.template_workbook(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="TASEMS-students-template.xlsx"'
    return response


@login_required
def student_import(request):
    branch = _branch_or_403(request, "people.add_student")
    session = _current_session()
    context = {"session": session, "max_rows": importer.MAX_ROWS}

    if request.method == "POST" and request.POST.get("step") == "check":
        upload = request.FILES.get("file")
        if upload is None or not upload.name.lower().endswith((".xlsx", ".pdf")):
            messages.error(request, _("Choose the Excel template (.xlsx) or the old software's PDF report."))
        elif upload.size > importer.MAX_BYTES:
            messages.error(request, _("The file is larger than 5 MB. Split it into smaller files."))
        else:
            content = upload.read()
            result = importer.check(content, branch=branch, session=session)
            token = ""
            if result.ok:
                token = secrets.token_hex(16)
                (_import_dir() / f"{token}.xlsx").write_bytes(content)
                request.session["import_token"] = {"token": token, "branch": branch.id, "name": upload.name}
            context.update(result=result, token=token, filename=upload.name, shown_errors=result.errors[:300])

    elif request.method == "POST" and request.POST.get("step") == "import":
        pending = request.session.pop("import_token", None)
        token = request.POST.get("token", "")
        if not pending or pending["token"] != token or pending["branch"] != branch.id or not token.isalnum():
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("people:student_import")
        path = _import_dir() / f"{token}.xlsx"
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("people:student_import")
        finally:
            path.unlink(missing_ok=True)
        result = importer.check(content, branch=branch, session=session)
        if not result.ok:
            messages.error(request, _("The data changed since the check. Please check the file again."))
            return redirect("people:student_import")
        count = importer.run_import(result, branch=branch, session=session, user=request.user)
        messages.success(request, _("%(n)s students imported.") % {"n": count})
        return redirect("people:student_list")

    return render(request, "people/student_import.html", context)
