"""Who may post notices where, who sees them, and read receipts (M8)."""

from django.db.models import Count, Q

from apps.accounts.models import RoleAssignment, Scope

from .models import Notice, NoticeRead

POST_PERM = "notices.add_notice"
SEND_PERM = "notices.send_messages"
TEMPLATE_PERM = "notices.change_messagetemplate"


def _scoped(user, scope, **target):
    return (
        user.is_superuser
        or RoleAssignment.objects.filter(
            user=user, is_active=True, scope=scope, role__permissions__codename="add_notice", **target
        ).exists()
    )


def can_edit_templates(user):
    return (
        user.is_superuser
        or RoleAssignment.objects.filter(
            user=user, is_active=True, scope=Scope.NETWORK, role__permissions__codename="change_messagetemplate"
        ).exists()
    )


def where_choices(user, branch):
    """[(value, label)] of the places this person may post a notice to, from the current branch."""
    from django.utils.translation import gettext as _

    out = []
    if user.has_branch_perm(POST_PERM, branch.id):
        out.append(("branch", branch.name))
    if _scoped(user, Scope.HEAD_OFFICE, head_office_id=branch.head_office_id):
        out.append(("head_office", _("Every branch of %(h)s") % {"h": branch.head_office.name}))
    if _scoped(user, Scope.NETWORK):
        out.append(("network", _("Every branch of the network")))
    return out


def may_manage(user, notice, branch):
    """Withdrawing a notice needs the same right as posting it there."""
    if notice.branch_id:
        return notice.branch_id == branch.id and user.has_branch_perm(POST_PERM, branch.id)
    if notice.head_office_id:
        return _scoped(user, Scope.HEAD_OFFICE, head_office_id=notice.head_office_id)
    return _scoped(user, Scope.NETWORK)


def staff_notices(branch, today):
    return (
        Notice.objects.for_branch(branch)
        .live(today)
        .filter(audience__in=[Notice.Audience.STAFF, Notice.Audience.EVERYONE])
    )


def parent_notices(children, today):
    """Notices for the parents of these children (their branches; the classes they are in now)."""
    from apps.people.models import Enrolment

    branches = {c.branch for c in children}
    levels = set(
        Enrolment.objects.filter(student__in=children, session__is_current=True).values_list(
            "section__class_level_id", flat=True
        )
    )
    q = Q(pk__in=[])
    for b in branches:
        q |= Q(pk__in=Notice.objects.for_branch(b).values("pk"))
    return (
        Notice.objects.filter(q)
        .live(today)
        .filter(audience__in=[Notice.Audience.PARENTS, Notice.Audience.EVERYONE])
        .annotate(n_levels=Count("class_levels"))
        .filter(Q(n_levels=0) | Q(class_levels__in=levels))
        .distinct()
        .order_by("-publish_on", "-pk")
    )


def mark_read(notice, user):
    NoticeRead.objects.get_or_create(notice=notice, user=user)


def unread_ids(notices, user):
    read = set(NoticeRead.objects.filter(user=user, notice__in=notices).values_list("notice_id", flat=True))
    return {n.id for n in notices if n.id not in read}
