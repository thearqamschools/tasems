from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.organisation.models import AcademicSession, Branch
from apps.people.models import Student, StudentGuardian

from .branch import current_branch, set_current_branch


@login_required
def home(request):
    """The dashboard: panels chosen by what the person may see (permissions, not role names)."""
    user = request.user
    if not user.accessible_branch_ids() and hasattr(user, "parent_account"):
        return redirect("parents:home")
    branch = current_branch(request)
    session = AcademicSession.objects.filter(is_current=True).first()
    today = timezone.localdate()
    context = {"branch": branch, "session": session, "today": today, "today_iso": today.isoformat()}
    if branch is None:
        return render(request, "core/home_no_access.html", context)

    from apps.dashboards import metrics

    def can(perm):
        return user.has_branch_perm(perm, branch.id)

    perms = {
        "students": can("people.view_student"),
        "attendance": can("attendance.view_attendancerecord"),
        "fees": can("fees.view_voucher"),
        "admissions": can("admissions.view_inquiry"),
        "staff": can("hr.view_employee"),
    }
    context["can"] = perms
    context["quick_actions"] = _quick_actions(user, branch, can)

    if perms["students"]:
        active = Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
        with_contact = StudentGuardian.objects.filter(student__in=active, is_primary_contact=True).values_list(
            "student_id", flat=True
        )
        enrolled_ids = active.filter(enrolments__session=session).values_list("id", flat=True) if session else []
        context["students"] = {
            "active": active.count(),
            "hifz": active.filter(is_hifz=True).count(),
            "no_contact": active.exclude(id__in=with_contact).count(),
            "not_enrolled": active.exclude(id__in=enrolled_ids).count() if session else None,
        }
    if session and perms["attendance"]:
        context["attendance"] = metrics.branch_today(branch, session, today)
        context["classes"] = metrics.classes_today(branch, session, today)
        context["attendance_trend"] = metrics.attendance_trend([branch.id], today)
    if perms["fees"]:
        context["fees"] = metrics.fee_month(branch, today)
    if perms["admissions"]:
        context["admissions"] = metrics.admissions(branch, today)
    if perms["staff"]:
        context["staff"] = metrics.staff_today(branch, today)

    my_sections = Section.objects.filter(class_teacher=user, is_active=True)
    if session:
        my_sections = my_sections.filter(session=session)
    my_sections = list(
        my_sections.select_related("class_level", "branch", "session").annotate(
            n=Count("enrolments", filter=Q(enrolments__student__status=Student.Status.ACTIVE))
        )
    )
    if my_sections:
        context["my_classes"] = metrics.my_classes(user, branch, my_sections, today)
    employee = getattr(user, "employee", None)
    if employee is not None:
        context["my_month"] = metrics.my_month(employee, today)

    branch_ids = user.accessible_branch_ids("people.view_student")
    if len(branch_ids) > 1:
        context.update(_network_context(request, user, branch_ids, session, today))
    context["has_money"] = "fees" in context or context.get("network_totals", {}).get("has_fees", False)
    return render(request, "core/home.html", context)


def _quick_actions(user, branch, can):
    from django.urls import reverse

    items = [
        ("attendance.view_attendancerecord", "attendance:today", _("Take registers"), "calendar-check"),
        ("diary.view_diary", "diary:day", _("Daily Diary"), "notebook-pen"),
        ("fees.add_payment", "fees:index", _("Receive a fee"), "wallet"),
        ("fees.add_voucher", "fees:generate", _("Make vouchers"), "receipt"),
        ("admissions.add_inquiry", "admissions:new", _("New inquiry"), "user-plus"),
        ("people.add_student", "people:student_create", _("Add a student"), "users"),
        ("hr.add_punch", "hr:punches_import", _("Import machine file"), "user-check"),
    ]
    actions = [(reverse(name), label, icon) for perm, name, label, icon in items if can(perm)]
    if getattr(user, "employee", None) is not None:
        actions.append((reverse("hr:mine"), _("My attendance"), "clock"))
    return actions[:6]


def _network_context(request, user, branch_ids, session, today):
    from apps.dashboards import metrics

    branches = Branch.objects.filter(id__in=branch_ids).select_related("head_office", "region").order_by("name")
    offices = sorted({b.head_office for b in branches}, key=lambda h: h.name)
    regions = sorted({b.region for b in branches if b.region}, key=lambda r: r.name)
    office_id, region_id = request.GET.get("ho", ""), request.GET.get("region", "")
    if office_id.isdigit():
        branches = branches.filter(head_office_id=int(office_id))
    if region_id.isdigit():
        branches = branches.filter(region_id=int(region_id))
    branches = list(branches)
    fee_ids = set(user.accessible_branch_ids("fees.view_voucher"))
    rows, totals = metrics.network(branches, session, today, fee_ids)
    royalty_ids = set(user.accessible_branch_ids("fees.view_royalty"))
    royalty_branches = [b for b in branches if b.id in royalty_ids]
    if royalty_branches:
        from apps.fees import reports

        # Same calculation as the Royalty page (D-040): each branch's percentage of fees received this month.
        totals["royalty"] = sum((r.royalty for r in reports.royalty(royalty_branches, today)), metrics.ZERO)
    sort = request.GET.get("sort", "attention")
    if sort not in metrics.SORTS:
        sort = "attention"
    rows.sort(key=metrics.SORTS[sort])
    show_all = request.GET.get("all") == "1"
    return {
        "network": rows if show_all else rows[:50],
        "network_more": 0 if show_all else max(0, len(rows) - 50),
        "network_totals": totals,
        "network_trend": metrics.attendance_trend([b.id for b in branches], today),
        "network_filters": {
            "offices": offices if len(offices) > 1 else [],
            "regions": regions,
            "ho": office_id,
            "region": region_id,
            "sort": sort,
        },
    }


@login_required
@require_POST
def switch_branch(request):
    if not set_current_branch(request, request.POST.get("branch", "")):
        messages.error(request, _("You do not have access to that branch."))
    back = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = "/"
    return redirect(back)


@login_required
def design_system(request):
    """Living style guide: every component of the design system with sample content (no school data).
    Staff accounts only; the reference for building new screens (docs/DESIGN_SYSTEM.md)."""
    from django.core.exceptions import PermissionDenied

    if not request.user.is_staff:
        raise PermissionDenied
    swatches = [
        ("--brand", "#3E4095", _("Primary (logo blue)")),
        ("--brand-strong", "#2B2D6E", _("Sidebar, hover")),
        ("--accent", "#ED3237", _("Accent (logo red)")),
        ("--ok", "#1F6B3A", _("Success")),
        ("--attention-bar", "#D99A1E", _("Needs attention")),
        ("--danger", "#B42318", _("Danger")),
        ("--ink", "#1D2238", _("Text")),
        ("--paper", "#F4F5FA", _("Page background")),
    ]
    import re

    from django.conf import settings

    sprite = (settings.BASE_DIR / "static" / "icons" / "icons.svg").read_text()
    icon_names = re.findall(r'<symbol id="i-([a-z0-9-]+)"', sprite)
    return render(request, "core/design_system.html", {"swatches": swatches, "icon_names": icon_names})


def health(request):
    """For uptime monitoring: 200 when the app and database answer, 503 otherwise. No login needed."""
    from django.db import connection
    from django.http import JsonResponse

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
    return JsonResponse({"status": "ok"})
