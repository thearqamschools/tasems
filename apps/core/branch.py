"""The branch a signed-in person is currently working in.

People with one branch never see a choice. Head office and regional staff pick a
branch from the switcher in the top bar; the choice is kept in their session.
"""

from apps.organisation.models import Branch

SESSION_KEY = "current_branch_id"


def accessible_branches(user):
    if not user.is_authenticated:
        return Branch.objects.none()
    return Branch.objects.filter(id__in=user.accessible_branch_ids(), is_active=True).order_by("name")


def current_branch(request):
    if hasattr(request, "_current_branch"):
        return request._current_branch
    branches = accessible_branches(request.user)
    chosen = request.session.get(SESSION_KEY)
    branch = branches.filter(id=chosen).first() if chosen else None
    if branch is None:
        branch = branches.first()
    request._current_branch = branch
    return branch


def set_current_branch(request, branch_id):
    if not str(branch_id).isdigit():
        return False
    if accessible_branches(request.user).filter(id=branch_id).exists():
        request.session[SESSION_KEY] = int(branch_id)
        return True
    return False
