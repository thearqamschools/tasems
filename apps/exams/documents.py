"""Date sheets, exam slips (admit cards) with photo, and award lists (M7)."""

from django.conf import settings
from django.template.loader import render_to_string

from apps.core import paths
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


def can_add_network_exams(user):
    from apps.accounts.models import RoleAssignment, Scope

    return (
        user.is_superuser
        or RoleAssignment.objects.filter(
            user=user, is_active=True, scope=Scope.NETWORK, role__permissions__codename="add_exam"
        ).exists()
    )


def can_see_question_paper(user, paper, branch):
    """A question paper is private until its exam day (R14-10 (7)): exam setup and principals see it any time;
    after the paper's date, anyone who may see exams does."""
    from django.utils import timezone

    if can_edit_date_sheet(user, paper.exam, branch) or user.has_branch_perm("exams.change_mark", branch.id):
        return True
    day = paper.date or paper.exam.ends_on
    return bool(day and day < timezone.localdate()) and user.has_branch_perm("exams.view_paper", branch.id)


def grid(exam, levels, short=False):
    """The printed date sheet (R14-5): a row per date from the first to the last day, a column per class, the
    subject(s) of each class on each date ("+" when two), "–" when none. No times."""
    import datetime as dt

    papers = list(exam.papers.filter(class_level__in=levels).select_related("subject", "class_level"))
    columns = sorted({p.class_level for p in papers}, key=lambda c: c.sort_order)
    first, last = exam.dates
    dated = sorted({p.date for p in papers if p.date})
    if first is None or last is None:
        days = dated
    else:
        days = [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]
        days = sorted(set(days) | set(dated))
    cell = {}
    for p in sorted(papers, key=lambda p: p.subject.name):
        if p.date:
            cell.setdefault((p.date, p.class_level_id), []).append(p.subject.short if short else p.subject.name)
    rows = [(d, [" + ".join(cell.get((d, c.id), [])) or "–" for c in columns]) for d in days]
    return {"columns": columns, "rows": rows, "first": first, "last": last}


def branch_address(branch):
    """The branch's address on one line (Setup → Branch details, R15-6) — no "Head Office" wording, no phones."""
    lines = [x.strip().rstrip(",") for x in (branch.address or "").splitlines() if x.strip()]
    return css_text(", ".join(lines))


def css_text(text):
    """Text placed inside a CSS string (page footer): no quotes, backslashes or angle brackets."""
    return "".join(ch for ch in text if ch not in '"\\<>')


def _fit(rows):
    """Row height so the whole date sheet stays on one A4 landscape page (R17-1); 128 mm are left for the rows."""
    rows = max(rows, 1)
    total = min(14.6, 128.0 / rows)  # each row's full height in mm
    pad = 1.6 if total >= 11 else 0.9 if total >= 7.5 else 0.5
    return {"row_h": f"{max(3.2, total):.1f}mm", "pad": f"{pad}mm", "compact": total < 9.5,
            "small": "8pt" if total < 7.5 else ""}  # fmt: skip


def date_sheet_pdf(exam, levels, branch):
    """The date sheet in the school's own colour design (lead, 27 Nov 2026: "Date Sheet — Colour A4 landscape")."""
    from weasyprint import HTML

    from apps.exams.models import PrintHeader
    from apps.exams.views_year import _campus_line

    sheet = grid(exam, levels, short=True)  # short subject names, as on the design (R19-5)
    rows = [(d, cells, all(c == "–" for c in cells)) for d, cells in sheet["rows"]]
    columns = len(sheet["columns"])
    header = PrintHeader.current()
    html = render_to_string(
        "exams/date_sheet_document.html",
        {
            "exam": exam,
            "branch": branch,
            "sheet": sheet,
            "rows": rows,
            "font": "10pt" if columns <= 11 else "9pt" if columns <= 13 else "8pt" if columns <= 16 else "7pt",
            "head_font": (
                "9.4pt" if columns <= 11 else "8.6pt" if columns <= 13 else "7.6pt" if columns <= 16 else "7pt"
            ),
            **_fit(len(rows)),
            "logo": paths.file_uri(paths.Path(settings.BASE_DIR) / "static" / "img" / "arqam-logo-512.png"),
            "header": paths.banner() if header is not None else "",
            "campus": _campus_line(branch),
            "font_base": paths.font_base(),
        },
    )
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


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
                {"e": e, "s": e.student, "photo": paths.file_uri(e.student.photo.path) if e.student.photo else ""}
                for e in enrolments
            ],
            "layout": DiaryLayout.current(),
            "font_base": paths.font_base(),
            "media_base": paths.media_base(),
        },
    )
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
