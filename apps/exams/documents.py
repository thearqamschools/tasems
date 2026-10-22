"""Date sheets, exam slips (admit cards) with photo, and award lists (M7)."""

from django.conf import settings
from django.template.loader import render_to_string

from apps.diary.models import DiaryLayout

PAPER_PERM = "exams.change_paper"


def can_edit_date_sheet(user, exam, branch):
    """A branch's own exam: whoever sets up exams for that branch. A network exam: only network-wide
    exam setup, because its dates print on every branch's slips."""
    if exam.branch_id:
        return exam.branch_id == branch.id and user.has_branch_perm(PAPER_PERM, branch.id)
    from apps.accounts.models import RoleAssignment, Scope

    return (
        user.is_superuser
        or RoleAssignment.objects.filter(
            user=user, is_active=True, scope=Scope.NETWORK, role__permissions__codename="change_paper"
        ).exists()
    )


def date_sheet(exam, levels):
    """[(class level, [papers in date order])] for the class levels given."""
    papers = exam.papers.filter(class_level__in=levels).select_related("subject", "class_level")
    by_level = {}
    for p in papers.order_by("class_level__sort_order", "date", "starts_at", "subject__name"):
        by_level.setdefault(p.class_level, []).append(p)
    return list(by_level.items())


def slips_pdf(exam, section, enrolments):
    from weasyprint import HTML

    papers = list(
        exam.papers.filter(class_level=section.class_level)
        .select_related("subject")
        .order_by("date", "starts_at", "subject__name")
    )
    html = render_to_string(
        "exams/slips_document.html",
        {
            "exam": exam,
            "section": section,
            "branch": section.branch,
            "papers": papers,
            "slips": [
                {"e": e, "s": e.student, "photo": f"file://{e.student.photo.path}" if e.student.photo else ""}
                for e in enrolments
            ],
            "layout": DiaryLayout.current(),
            "font_base": f"file://{settings.BASE_DIR}/static/fonts/",
            "media_base": f"file://{settings.MEDIA_ROOT}/",
        },
    )
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
