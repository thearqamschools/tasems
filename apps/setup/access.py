"""Who may change setup, and who may give access to whom (DECISIONS D-066).

The rule that keeps access safe: **nobody can give more than they hold.**
A role may be assigned at a scope only when the person assigning it
  1. may assign roles (`accounts.add_roleassignment`) over every branch that scope covers, and
  2. holds every *guarded* permission of that role over every branch that scope covers.
Guarded permissions control access and structure (accounts, auth, organisation, core incl. the audit log)
and anything that deletes. Day-to-day work permissions (taking attendance, collecting fees) are not
guarded: administrators deliberately do not hold them, yet must be able to appoint the people who do.
People never change their own access, and only a superuser changes a superuser.
"""

from django.db.models import Q

from apps.accounts.models import Role, Scope, User
from apps.organisation.models import Branch, HeadOffice, Region

ASSIGN_PERM = "accounts.add_roleassignment"
END_PERM = "accounts.change_roleassignment"
VIEW_USERS_PERM = "accounts.view_user"
ADD_USER_PERM = "accounts.add_user"
CHANGE_USER_PERM = "accounts.change_user"
GUARDED_APPS = {"accounts", "auth", "organisation", "core", "admin", "contenttypes", "sessions"}


def guarded(perm):
    app, codename = perm.split(".", 1)
    return app in GUARDED_APPS or codename.startswith("delete_")


def scope_branch_ids(scope, head_office=None, region=None, branch=None):
    """Branches a scope covers (inactive branches included: access to them is still access)."""
    branches = Branch.objects.all()
    if scope == Scope.NETWORK:
        return set(branches.values_list("id", flat=True))
    if scope == Scope.HEAD_OFFICE and head_office is not None:
        return set(branches.filter(head_office=head_office).values_list("id", flat=True))
    if scope == Scope.REGION and region is not None:
        return set(branches.filter(region=region).values_list("id", flat=True))
    if scope == Scope.BRANCH and branch is not None:
        return {branch.id}
    return set()


def assignment_branch_ids(a):
    return scope_branch_ids(a.scope, a.head_office, a.region, a.branch)


def covers(user, permission, branch_ids):
    """True if `user` holds `permission` over every branch in `branch_ids`.
    An empty set (e.g. a head office with no branches yet) needs network-wide access."""
    if user.is_superuser and user.is_active:
        return True
    held = user.accessible_branch_ids(permission)
    if not branch_ids:
        return held == set(Branch.objects.values_list("id", flat=True)) and bool(held)
    return branch_ids <= held


def _perm_names(role):
    return {f"{p.content_type.app_label}.{p.codename}" for p in role.permissions.select_related("content_type")}


def can_assign(grantor, role, scope, branch_ids):
    """(allowed, reason). See the module docstring."""
    if role.allowed_scopes and scope not in role.allowed_scopes:
        return False, "scope"
    if not covers(grantor, ASSIGN_PERM, branch_ids):
        return False, "outside"
    if grantor.is_superuser:
        return True, ""
    for perm in filter(guarded, _perm_names(role)):
        if not covers(grantor, perm, branch_ids):
            return False, "more_than_you_hold"
    return True, ""


def assignable_roles(grantor, scope, branch_ids):
    return [
        r
        for r in Role.objects.prefetch_related("permissions__content_type")
        if can_assign(grantor, r, scope, branch_ids)[0]
    ]


def scope_targets(grantor):
    """Head offices, regions and branches the grantor may assign roles in (for the form's choices)."""
    ids = grantor.accessible_branch_ids(ASSIGN_PERM) if not grantor.is_superuser else None
    branches = Branch.objects.all() if ids is None else Branch.objects.filter(id__in=ids)
    offices = [
        h for h in HeadOffice.objects.all() if covers(grantor, ASSIGN_PERM, scope_branch_ids(Scope.HEAD_OFFICE, h))
    ]
    regions = [
        r
        for r in Region.objects.select_related("head_office")
        if covers(grantor, ASSIGN_PERM, scope_branch_ids(Scope.REGION, region=r))
    ]
    network = covers(grantor, ASSIGN_PERM, scope_branch_ids(Scope.NETWORK))
    return {
        "network": network,
        "head_offices": offices,
        "regions": regions,
        "branches": list(branches.select_related("head_office").order_by("head_office__name", "name")),
    }


def visible_users(viewer):
    """Users with at least one role (active or ended) touching a branch the viewer may see users in."""
    if viewer.is_superuser:
        return User.objects.all()
    ids = viewer.accessible_branch_ids(VIEW_USERS_PERM)
    if not ids:
        return User.objects.none()
    branches = Branch.objects.filter(id__in=ids)
    cond = (
        Q(role_assignments__branch_id__in=ids)
        | Q(role_assignments__region_id__in=branches.exclude(region=None).values("region_id"))
        | Q(role_assignments__head_office_id__in=branches.values("head_office_id"))
    )
    if covers(viewer, VIEW_USERS_PERM, scope_branch_ids(Scope.NETWORK)):
        cond |= Q(role_assignments__scope=Scope.NETWORK)
    return User.objects.filter(cond).distinct()


def can_manage_user(manager, target, permission=CHANGE_USER_PERM):
    """Change someone's details, password or active state: not yourself, never a superuser (unless you are one),
    and only if every role they hold lies inside your area — so nobody can lock out or take over a person
    who also works elsewhere."""
    if target.pk == manager.pk:
        return False
    if target.is_superuser and not manager.is_superuser:
        return False
    if manager.is_superuser:
        return True
    assignments = list(target.role_assignments.filter(is_active=True))
    if not assignments:
        return False
    return all(covers(manager, permission, assignment_branch_ids(a)) for a in assignments)


def can_end(manager, assignment):
    if assignment.user_id == manager.pk:
        return False
    if assignment.user.is_superuser and not manager.is_superuser:
        return False
    return covers(manager, END_PERM, assignment_branch_ids(assignment))
