"""Student register: list, view, add, edit and Excel import for the current branch."""

import secrets
import time
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.db.models.functions import Length
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.academics.models import ClassLevel, Section
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.organisation.models import AcademicSession

from . import importer
from .forms import StudentForm, section_order
from .models import Enrolment, Student, StudentGuardian
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
            "can_edit": can_edit,
            "history": history,
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
        request.POST or None, instance=student, initial=initial, branch=branch, session=session, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save_all()
        messages.success(request, _("Saved %(name)s.") % {"name": saved.full_name})
        return redirect("people:student_detail", pk=saved.pk)
    return render(request, "people/student_form.html", {"form": form, "student": student, "session": session})


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
