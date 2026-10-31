"""Student register: list, view, add, edit and Excel import for the current branch."""

import secrets
import time
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch
from django.db.models.functions import Length
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.academics.models import ClassLevel, Section
from apps.core import escpos, exports
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.fees.services import balance as fee_balance
from apps.organisation.models import AcademicSession, Campus

from . import certificates, idcards, importer
from . import promotion as promote
from .forms import CertificateForm, LeaveForm, StudentForm, section_order
from .models import Certificate, Enrolment, Student, StudentGuardian
from .services import current_enrolment, parent_mobiles, place_filter
from .services import search as search_students

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
    students = search_students(students, q)

    sections = Section.objects.filter(branch=branch, session=session) if session else Section.objects.none()
    section_names = sorted(set(sections.values_list("name", flat=True)), key=section_order)
    section_name = request.GET.get("section", "")
    level_id = request.GET.get("class", "")
    campus_id = request.GET.get("campus", "")
    students = place_filter(students, session, level_id, section_name, campus_id)

    enrolments = Enrolment.objects.filter(session=session).select_related("section__class_level") if session else []
    students = students.prefetch_related(
        Prefetch("enrolments", queryset=enrolments, to_attr="current_enrolments") if session else "enrolments",
        Prefetch(
            "guardian_links",
            queryset=StudentGuardian.objects.select_related("guardian"),
            to_attr="contact_links",
        ),
    ).order_by(Length("admission_no"), "admission_no")

    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Students"),
            [_("Admission no."), _("Name"), _("Father name"), _("Class"), _("Section"), _("Parent mobile"),
             _("Father CNIC"), _("Gender"), _("Date of birth"), _("Admission date"), _("Status")],
            (
                [
                    st.admission_no,
                    st.full_name,
                    st.father_name,
                    *(
                        [st.current_enrolments[0].section.class_level.name, st.current_enrolments[0].section.name]
                        if session and st.current_enrolments
                        else ["", ""]
                    ),
                    ", ".join(parent_mobiles(st)),
                    st.father_cnic,
                    st.get_gender_display(),
                    st.date_of_birth,
                    st.admission_date,
                    st.get_status_display(),
                ]
                for st in students
            ),
            branch=branch,
        )  # fmt: skip
    page = exports.paginate(request, students, PAGE_SIZE)
    page.object_list = list(page.object_list)
    for st in page.object_list:
        st.parent_mobiles = parent_mobiles(st)
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
            "campuses": Campus.objects.filter(branch=branch, is_active=True),
            "campus_id": campus_id,
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
            "hifz": request.user.has_branch_perm("hifz.view_hifzlesson", student.branch_id)
            and (student.is_hifz or student.enrolments.filter(section__class_level__code="hifz").exists()),
        },
    )


def _parent_tree_rows(student):
    """The child and every brother and sister still at school (same father CNIC), higher class first."""
    session = _current_session()
    rows = []
    for child in [student, *student.siblings().filter(status=Student.Status.ACTIVE)]:
        enrolment = current_enrolment(child, session) if session else None
        section = enrolment.section if enrolment else None
        campus = section.campus.name if section and section.campus else ""
        rows.append(
            {
                "campus": campus.removesuffix(" Campus").removesuffix(" campus"),
                "code": child.admission_no,
                "name": child.full_name,
                "class": section.class_level.name if section else "",
                "section": section.name if section else "",
                "order": -section.class_level.sort_order if section else 0,
            }
        )
    rows.sort(key=lambda r: (r["order"], r["name"]))
    return rows


@login_required
def parent_tree(request, pk):
    """Parent Tree slip, used to call children out of class (project lead, 28 Oct 2026). Only for a current student.
    POST: printed straight on the branch's network receipt printer, with no print window. GET: the slip on screen
    (80 mm), for a printer that is not on the network."""
    branch = _branch_or_403(request, "people.view_student")
    student = _get_student(request, pk, branch)
    if student.status != Student.Status.ACTIVE:
        raise Http404
    rows, now = _parent_tree_rows(student), timezone.localtime()
    if request.method != "POST":
        return render(
            request,
            "people/parent_tree.html",
            {"student": student, "branch": student.branch, "rows": rows, "printed_at": now},
        )
    printer = student.branch.receipt_printer
    if not printer:
        ok, text = False, _("No receipt printer is set for this branch. Find it in Setup → Receipt printer.")
    else:
        try:
            escpos.send(
                printer,
                escpos.parent_tree(
                    student.branch,
                    student.father_name,
                    now,
                    rows,
                    request.user.get_full_name() or request.user.username,
                ),
            )
            ok = True
            text = ngettext(
                "Parent Tree printed: %(n)s student.", "Parent Tree printed: %(n)s students.", len(rows)
            ) % {"n": len(rows)}
        except escpos.PrinterError as error:
            ok, text = (
                False,
                _("The receipt printer (%(p)s) did not answer: %(e)s. Check that it is on and connected.")
                % {
                    "p": printer,
                    "e": error,
                },
            )
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": ok, "message": text}, status=200 if ok else 503)
    (messages.success if ok else messages.error)(request, text)
    back = request.POST.get("next", "")
    return redirect(back if url_has_allowed_host_and_scheme(back, {request.get_host()}) else "people:student_list")


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


def skipped_message(rows):
    """Told after an import that left out the rows with problems, so they can be fixed and imported later."""
    shown = ", ".join(str(r) for r in rows[:30]) + (" …" if len(rows) > 30 else "")
    return ngettext(
        "Row %(rows)s was not imported because of its problem. Correct it and import it again.",
        "%(n)s rows were not imported because of their problems (rows %(rows)s). Correct them and import them again.",
        len(rows),
    ) % {"n": len(rows), "rows": shown}


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
            if result.ok or result.can_skip:
                token = secrets.token_hex(16)
                (_import_dir() / f"{token}.xlsx").write_bytes(content)
                request.session["import_token"] = {"token": token, "branch": branch.id, "name": upload.name}
            context.update(result=result, token=token, filename=upload.name, shown_errors=result.errors[:300])
            if result.can_skip:
                context.update(skip_count=len(result.problem_rows), keep_count=len(result.without_problem_rows().rows))

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
        skipped = []
        if request.POST.get("skip") == "1" and result.can_skip:
            skipped = result.problem_rows
            result = result.without_problem_rows()
        if not result.ok:
            messages.error(request, _("The data changed since the check. Please check the file again."))
            return redirect("people:student_import")
        count = importer.run_import(result, branch=branch, session=session, user=request.user)
        messages.success(request, _("%(n)s students imported.") % {"n": count})
        if skipped:
            messages.warning(request, skipped_message(skipped))
        return redirect("people:student_list")

    return render(request, "people/student_import.html", context)
