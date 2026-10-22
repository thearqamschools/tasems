"""Reports centre (M6) and the reports that were missing: class strength, new admissions, monthly attendance."""

import datetime as dt

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.academics.models import Section
from apps.core import exports
from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession
from apps.people.models import Student

from . import catalogue


def _branch(request, perm=None):
    branch = current_branch(request)
    if branch is None or (perm and not request.user.has_branch_perm(perm, branch.id)):
        raise PermissionDenied
    return branch


def _session():
    return AcademicSession.objects.filter(is_current=True).first()


def _date(value, default):
    try:
        return dt.date.fromisoformat(value) if value else default
    except ValueError:
        return default


@login_required
def index(request):
    branch = _branch(request)
    modules = catalogue.build(request.user, branch, _session(), timezone.localdate())
    if not modules:
        raise PermissionDenied
    return render(request, "reports/index.html", {"branch": branch, "modules": modules})


@login_required
def class_strength(request):
    branch = _branch(request, "people.view_student")
    session = _session()
    active = Q(enrolments__student__status=Student.Status.ACTIVE)
    sections = (
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level", "campus")
        .annotate(
            boys=Count("enrolments", filter=active & Q(enrolments__student__gender="male")),
            girls=Count("enrolments", filter=active & Q(enrolments__student__gender="female")),
            hifz=Count("enrolments", filter=active & Q(enrolments__student__is_hifz=True)),
        )
        .order_by("class_level__sort_order", "name")
        if session
        else Section.objects.none()
    )
    rows = [
        {"section": s, "boys": s.boys, "girls": s.girls, "hifz": s.hifz, "total": s.boys + s.girls} for s in sections
    ]
    totals = {k: sum(r[k] for r in rows) for k in ("boys", "girls", "hifz", "total")}
    unplaced = (
        Student.objects.filter(branch=branch, status=Student.Status.ACTIVE).exclude(enrolments__session=session).count()
        if session
        else 0
    )
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Class strength"),
            [_("Class"), _("Section"), _("Campus"), _("Boys"), _("Girls"), _("Total"), _("Hifz")],
            [
                *([r["section"].class_level.name, r["section"].name, str(r["section"].campus or ""), r["boys"],
                   r["girls"], r["total"], r["hifz"]] for r in rows),
                [_("Total"), "", "", totals["boys"], totals["girls"], totals["total"], totals["hifz"]],
            ],
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "reports/class_strength.html",
        {"branch": branch, "session": session, "rows": rows, "totals": totals, "unplaced": unplaced},
    )


@login_required
def new_admissions(request):
    branch = _branch(request, "people.view_student")
    today = timezone.localdate()
    start = _date(request.GET.get("from"), today.replace(day=1))
    end = _date(request.GET.get("to"), today)
    if end < start:
        start, end = end, start
    session = _session()
    students = (
        Student.objects.filter(branch=branch, admission_date__gte=start, admission_date__lte=end)
        .prefetch_related("enrolments__section__class_level")
        .order_by("admission_date", "admission_no")
    )
    rows = []
    for s in students:
        enrolment = next((e for e in s.enrolments.all() if session and e.session_id == session.id), None)
        rows.append({"student": s, "section": enrolment.section if enrolment else None})
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("New admissions") + f" {start:%d-%m-%Y} to {end:%d-%m-%Y}",
            [_("Admission date"), _("Admission no."), _("Name"), _("Father name"), _("Gender"), _("Class"),
             _("Section"), _("Hifz"), _("Status")],
            (
                [r["student"].admission_date, r["student"].admission_no, r["student"].full_name,
                 r["student"].father_name, r["student"].get_gender_display(),
                 r["section"].class_level.name if r["section"] else "", r["section"].name if r["section"] else "",
                 _("Yes") if r["student"].is_hifz else "", r["student"].get_status_display()]
                for r in rows
            ),
            branch=branch,
        )  # fmt: skip
    return render(request, "reports/new_admissions.html", {"rows": rows, "start": start, "end": end})


@login_required
def attendance_month(request):
    branch = _branch(request, "attendance.view_attendancerecord")
    month, next_month = catalogue.month_bounds(request.GET.get("month"), timezone.localdate())
    session = _session()
    rows = catalogue.attendance_rows(branch, session, month, next_month) if session else []
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Monthly attendance by class") + f" {month:%b %Y}",
            [_("Class"), _("Section"), _("Register days"), _("Attendance %"), _("Absences"), _("Leave"), _("Late")],
            (
                [r["section"].class_level.name, r["section"].name, r["days"], r["rate"], r["absent"], r["leave"],
                 r["late"]]
                for r in rows
            ),
            branch=branch,
        )  # fmt: skip
    return render(request, "reports/attendance_month.html", {"rows": rows, "month": month})
