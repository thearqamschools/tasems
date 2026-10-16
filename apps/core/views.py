from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
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
    context = {"branch": branch, "session": session, "active_count": None}

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
        rows = [
            (b, counts.get(b.id, 0))
            for b in Branch.objects.filter(id__in=branch_ids).select_related("head_office", "region")
        ]
        rows.sort(key=lambda r: (-r[1], r[0].name))
        context["network"] = rows[:50]
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
