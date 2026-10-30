"""Deleting a record made by mistake (project lead, 23 Oct 2026).

The master login and head office may delete anything in the branches they look after; a branch's Director may
delete anything in that branch. Branches, regions, sessions, users and network lists also need the matching
setup right. A record is deleted together with the parts that only exist for it (e.g. a student's class
places); anything with history — fees, attendance, marks, stock moves — stops the deletion, and the page says
what is in the way. Every deletion is written to the history with its reason."""

from dataclasses import dataclass, field

from django.apps import apps
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.setup import access

from .models import AuditEvent

DELETE_PERM = "core.delete_records"


@dataclass(frozen=True)
class Entry:
    model: str
    label: object
    back: str
    extra_perm: str = ""
    first: tuple = field(default_factory=tuple)  # parts deleted together with the record

    def get_model(self):
        return apps.get_model(self.model)


REGISTRY = {
    "branch": Entry("organisation.Branch", _("branch"), "setup:branches", "organisation.change_branch", ("campuses",)),
    "region": Entry("organisation.Region", _("region"), "setup:branches", "organisation.change_region"),
    "session": Entry(
        "organisation.AcademicSession", _("academic session"), "setup:sessions", "organisation.change_academicsession"
    ),  # fmt: skip
    "campus": Entry("organisation.Campus", _("campus"), "setup:sections"),
    "section": Entry("academics.Section", _("section"), "setup:sections"),
    "feerate": Entry("fees.FeeRate", _("fee rate"), "setup:fees"),
    "bank": Entry("fees.BankAccount", _("bank"), "setup:fees"),
    "discounttype": Entry("fees.DiscountType", _("discount type"), "setup:fees", "fees.change_feehead"),
    "user": Entry("accounts.User", _("login"), "setup:users", "accounts.change_user"),
    "student": Entry("people.Student", _("student"), "people:student_list", first=("enrolments",)),
    "employee": Entry("hr.Employee", _("staff member"), "hr:index"),
    "inquiry": Entry("admissions.Inquiry", _("admission inquiry"), "admissions:index"),
    "item": Entry("inventory.Item", _("item"), "inventory:index"),
    "notice": Entry("notices.Notice", _("notice"), "notices:index"),
    "event": Entry("events.Event", _("event"), "events:index", first=("classes",)),
}


def kind_of(obj):
    """The registry name for a saved record, or None when it cannot be deleted from the screens."""
    if obj is None or getattr(obj, "pk", None) is None:
        return None
    label = obj._meta.label
    return next((kind for kind, entry in REGISTRY.items() if entry.model == label), None)


def branch_ids(kind, obj):
    """Branches the record belongs to; an empty set means network-wide (needs network-wide rights)."""
    from apps.organisation.models import Branch

    if kind == "branch":
        return {obj.id}
    if kind == "region":
        return set(Branch.objects.filter(head_office_id=obj.head_office_id).values_list("id", flat=True))
    if kind == "user":
        ids = set()
        for a in obj.role_assignments.all():
            covered = access.assignment_branch_ids(a)
            if a.scope == "network":
                return set()
            ids |= covered
        return ids
    branch_id = getattr(obj, "branch_id", None)
    if branch_id:
        return {branch_id}
    if getattr(obj, "head_office_id", None):  # e.g. a notice for every branch of one head office
        return set(Branch.objects.filter(head_office_id=obj.head_office_id).values_list("id", flat=True))
    return set()


def can_delete(user, kind, obj):
    entry = REGISTRY[kind]
    if not user.is_authenticated or not user.is_active:
        return False
    if kind == "user" and (obj.pk == user.pk or (obj.is_superuser and not user.is_superuser)):
        return False  # nobody deletes themselves; only a superuser deletes a superuser
    ids = branch_ids(kind, obj)
    if not access.covers(user, DELETE_PERM, ids):
        return False
    return not entry.extra_perm or access.covers(user, entry.extra_perm, ids)


def _remove(kind, obj):
    entry = REGISTRY[kind]
    removed = {}
    for related in entry.first:
        _total, counts = getattr(obj, related).all().delete()
        for label, n in counts.items():
            removed[label] = removed.get(label, 0) + n
    _total, counts = obj.delete()
    for label, n in counts.items():
        removed[label] = removed.get(label, 0) + n
    return removed


class _DryRun(Exception):
    def __init__(self, removed):
        self.removed = removed


def _names(counts):
    out = []
    for label, n in sorted(counts.items()):
        if not n:
            continue
        meta = apps.get_model(label)._meta
        out.append((meta.verbose_name if n == 1 else meta.verbose_name_plural, n))
    return out


def _blockers(error):
    found = {}
    for o in list(error.protected_objects if isinstance(error, ProtectedError) else error.restricted_objects):
        found[o._meta.label] = found.get(o._meta.label, 0) + 1
    return _names(found)


def preview(kind, obj):
    """(what would be removed, what is in the way) without changing anything."""
    try:
        with transaction.atomic():
            raise _DryRun(_remove(kind, obj))
    except _DryRun as done:
        return _names(done.removed), []
    except (ProtectedError, RestrictedError) as error:
        return [], _blockers(error)


def delete(kind, obj, user, reason):
    """Deletes and records it. Raises ProtectedError/RestrictedError if something is in the way."""
    label, object_id, text = obj._meta.label, str(obj.pk), str(obj)[:255]
    ids = branch_ids(kind, obj)
    with transaction.atomic():
        removed = _remove(kind, obj)
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.DELETE,
            model_label=label,
            object_id=object_id,
            object_repr=text,
            branch_id=next(iter(ids)) if len(ids) == 1 else None,
            changes={"reason": reason, "removed": removed},
        )
    return removed


def back_url(kind):
    return reverse(REGISTRY[kind].back)
