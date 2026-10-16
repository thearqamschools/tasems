from django.urls import reverse
from django.utils.translation import gettext as _

from apps.core.branch import accessible_branches, current_branch

MAX_SWITCHER_BRANCHES = 400


def navigation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    branch = current_branch(request)
    path = request.path
    items = [(reverse("home"), _("Home"), path == reverse("home"))]
    if branch and user.has_branch_perm("people.view_student", branch.id):
        url = reverse("people:student_list")
        items.append((url, _("Students"), path.startswith(url) and "import" not in path))
    if branch and user.has_branch_perm("attendance.view_attendancerecord", branch.id):
        url = reverse("attendance:today")
        items.append((url, _("Attendance"), path.startswith(url)))
    if branch and user.has_branch_perm("people.add_student", branch.id):
        url = reverse("people:student_import")
        items.append((url, _("Import from Excel"), path.startswith(url)))
    if user.is_staff:
        items.append(("/admin/", _("Setup"), path.startswith("/admin/")))
    return {
        "current_branch": branch,
        "switchable_branches": list(accessible_branches(user)[:MAX_SWITCHER_BRANCHES]),
        "nav_items": [{"url": u, "label": label, "active": active} for u, label, active in items],
    }
