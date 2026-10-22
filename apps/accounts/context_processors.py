from django.urls import reverse
from django.utils.translation import gettext as _

from apps.core.branch import accessible_branches, current_branch
from apps.organisation.models import AcademicSession

MAX_SWITCHER_BRANCHES = 400


def _menu(user, branch):
    """The sidebar: groups of (url, label, icon). Only pages this user may open are listed; every
    item uses the same permission the page itself checks, so the menu never leads to a refusal."""

    def perm(name):
        return branch is not None and user.has_branch_perm(name, branch.id)

    groups = []

    def group(label, items):
        items = [i for i in items if i]
        if items:
            groups.append((label, items))

    group(_("Overview"), [(reverse("home"), _("Dashboard"), "layout-dashboard")])

    attendance_items = []
    if perm("attendance.view_attendancerecord"):
        attendance_items = [
            (reverse("attendance:today"), _("Attendance"), "calendar-check"),
            (reverse("attendance:absentees"), _("Absent students"), "circle-alert"),
        ]
        if len(user.accessible_branch_ids("attendance.view_attendancerecord")) > 1:
            attendance_items.append((reverse("attendance:branches"), _("All my branches"), "building-2"))
    group(
        _("Students"),
        [
            perm("people.view_student") and (reverse("people:student_list"), _("Students"), "users"),
            perm("admissions.view_inquiry") and (reverse("admissions:index"), _("Admission inquiries"), "user-plus"),
            perm("admissions.view_inquiry") and (reverse("admissions:report"), _("Admissions report"), "file-text"),
            *attendance_items,
            perm("people.add_student")
            and (reverse("people:student_import"), _("Import from Excel"), "file-spreadsheet"),
            perm("people.add_enrolment") and (reverse("people:promotion"), _("Promotion"), "graduation-cap"),
        ],
    )
    group(
        _("Academics"),
        [
            perm("diary.view_diary") and (reverse("diary:day"), _("Daily Diary"), "notebook-pen"),
            perm("exams.view_mark") and (reverse("exams:index"), _("Exams & Results"), "graduation-cap"),
        ],
    )
    fees = perm("fees.view_voucher")
    group(
        _("Finance"),
        [
            perm("fees.add_payment") and (reverse("fees:quick"), _("Barcode"), "scan-barcode"),
            fees and (reverse("fees:index"), _("Fees"), "wallet"),
            perm("fees.add_voucher") and (reverse("fees:generate"), _("Generate vouchers"), "receipt"),
            fees and (reverse("fees:vouchers"), _("Vouchers"), "list-checks"),
            fees and (reverse("fees:defaulters"), _("Defaulters"), "triangle-alert"),
            fees and (reverse("fees:collections"), _("Daily collection"), "coins"),
            fees and (reverse("fees:concessions"), _("Discounts"), "badge-percent"),
            perm("accounting.view_expense") and (reverse("accounting:index"), _("Expenses"), "receipt"),
            bool(user.accessible_branch_ids("fees.view_royalty"))
            and (reverse("fees:royalty"), _("Royalty"), "landmark"),
        ],
    )
    staff = perm("hr.view_employee")
    group(
        _("Staff"),
        [
            staff and (reverse("hr:index"), _("Staff"), "briefcase"),
            staff and (reverse("hr:day"), _("Staff attendance"), "user-check"),
            staff and (reverse("hr:month"), _("Monthly sheet"), "file-spreadsheet"),
            staff and (reverse("hr:leaves"), _("Leave"), "inbox"),
            getattr(user, "employee", None) is not None and (reverse("hr:mine"), _("My attendance"), "clock"),
        ],
    )
    can_setup = (
        user.is_superuser
        or perm("academics.change_section")
        or perm("fees.change_feerate")
        or bool(user.accessible_branch_ids("accounts.view_user"))
        or bool(user.accessible_branch_ids("organisation.change_branch"))
    )
    group(
        _("Settings"),
        [
            can_setup and (reverse("setup:hub"), _("Setup"), "settings"),
            user.is_staff and ("/admin/", _("Advanced setup"), "file-text"),
            user.is_staff and (reverse("design_system"), _("Design system"), "palette"),
        ],
    )
    return groups


def navigation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    branch = current_branch(request)
    path = request.path
    groups = _menu(user, branch)

    # The active item is the one whose address matches the current page most closely.
    urls = [url for _label, items in groups for url, _l, _i in items]
    home = reverse("home")
    matches = [u for u in urls if (path == u if u == home else path.startswith(u))]
    active = max(matches, key=len) if matches else None

    nav_groups = []
    for label, items in groups:
        entries = [{"url": u, "label": text, "icon": ic, "active": u == active} for u, text, ic in items]
        nav_groups.append({"label": label, "items": entries, "open": any(e["active"] for e in entries)})

    switchable = list(
        accessible_branches(user)
        .select_related("head_office", "region")
        .order_by("head_office__name", "region__name", "name")[:MAX_SWITCHER_BRANCHES]
    )
    return {
        "current_branch": branch,
        "current_session": AcademicSession.objects.filter(is_current=True).first(),
        # Top-bar search opens the student list (same search as on that page).
        "can_search_students": branch is not None and user.has_branch_perm("people.view_student", branch.id),
        "switchable_branches": switchable,
        "nav_groups": nav_groups,
        # Flat list kept for any page that still reads it.
        "nav_items": [e for g in nav_groups for e in g["items"]],
    }
