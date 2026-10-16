from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import ClassLevel, Section
from apps.organisation.models import AcademicSession, Branch
from apps.people.models import Student, StudentGuardian

from .branch import current_branch, set_current_branch


@login_required
def home(request):
    user = request.user
    branch = current_branch(request)
    session = AcademicSession.objects.filter(is_current=True).first()
    context = {
        "branch": branch,
        "session": session,
        "active_count": None,
        "today_iso": timezone.localdate().isoformat(),
    }

    if branch is None:
        return render(request, "core/home_no_access.html", context)

    if user.has_branch_perm("people.view_student", branch.id):
        students = Student.objects.filter(branch=branch)
        active = students.filter(status=Student.Status.ACTIVE)
        with_contact = StudentGuardian.objects.filter(student__in=active, is_primary_contact=True).values_list(
            "student_id", flat=True
        )
        enrolled_ids = active.filter(enrolments__session=session).values_list("id", flat=True) if session else []
        by_stage = (
            active.filter(enrolments__session=session)
            .values("enrolments__section__class_level__stage")
            .annotate(n=Count("id"))
            if session
            else []
        )
        stage_labels = dict(ClassLevel.Stage.choices)
        context.update(
            {
                "active_count": active.count(),
                "hifz_count": active.filter(is_hifz=True).count(),
                "no_contact_count": active.exclude(id__in=with_contact).count(),
                "not_enrolled_count": active.exclude(id__in=enrolled_ids).count() if session else None,
                "by_stage": [
                    (stage_labels.get(row["enrolments__section__class_level__stage"], "—"), row["n"])
                    for row in by_stage
                ],
            }
        )
    if session and user.has_branch_perm("attendance.view_attendancerecord", branch.id):
        from apps.attendance.models import SectionAttendance

        today = timezone.localdate()
        context["registers_taken"] = SectionAttendance.objects.filter(branch=branch, date=today).count()
        from apps.attendance.services import in_school

        sections_today = Section.objects.filter(branch=branch, session=session, is_active=True)
        context["registers_total"] = in_school(sections_today, today).count()
    my_sections = Section.objects.filter(class_teacher=user, is_active=True)
    if session:
        my_sections = my_sections.filter(session=session)
    context["my_sections"] = my_sections.select_related("class_level", "branch").annotate(
        n=Count("enrolments", filter=Q(enrolments__student__status=Student.Status.ACTIVE))
    )

    branch_ids = user.accessible_branch_ids("people.view_student")
    if len(branch_ids) > 1:
        counts = dict(
            Student.objects.filter(branch_id__in=branch_ids, status=Student.Status.ACTIVE)
            .values("branch_id")
            .annotate(n=Count("id"))
            .values_list("branch_id", "n")
        )
        today = timezone.localdate()
        registers, sections_due, diaries = {}, {}, {}
        if session:
            from apps.attendance.models import SectionAttendance
            from apps.attendance.services import in_school
            from apps.diary.models import Diary

            registers = dict(
                SectionAttendance.objects.filter(branch_id__in=branch_ids, date=today)
                .values("branch_id")
                .annotate(n=Count("id"))
                .values_list("branch_id", "n")
            )
            sections_due = dict(
                in_school(Section.objects.filter(branch_id__in=branch_ids, session=session, is_active=True), today)
                .values("branch_id")
                .annotate(n=Count("id"))
                .values_list("branch_id", "n")
            )
            diaries = dict(
                Diary.objects.filter(branch_id__in=branch_ids, date=today, status=Diary.Status.PUBLISHED)
                .values("branch_id")
                .annotate(n=Count("id"))
                .values_list("branch_id", "n")
            )
        rows = [
            {
                "branch": b,
                "students": counts.get(b.id, 0),
                "registers": registers.get(b.id, 0),
                "sections": sections_due.get(b.id, 0),
                "diaries": diaries.get(b.id, 0),
            }
            for b in Branch.objects.filter(id__in=branch_ids).select_related("head_office", "region")
        ]
        # Branches that have not started today's registers first, then the largest.
        rows.sort(
            key=lambda r: (not (r["sections"] and r["registers"] < r["sections"]), -r["students"], r["branch"].name)
        )
        context["network"] = rows[:50]
        context["network_registers"] = sum(registers.values())
        context["network_sections"] = sum(sections_due.values())
        context["network_diaries"] = sum(diaries.values())
        context["network_students"] = sum(counts.values())
        context["network_total_branches"] = len(branch_ids)
    return render(request, "core/home.html", context)


@login_required
@require_POST
def switch_branch(request):
    if not set_current_branch(request, request.POST.get("branch", "")):
        messages.error(request, _("You do not have access to that branch."))
    back = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = "/"
    return redirect(back)


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
