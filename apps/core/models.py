"""Shared building blocks used by every TASEMS module."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BranchScopedQuerySet(models.QuerySet):
    """Every branch-owned table is read through `.for_user(user)`.

    This is the application-level lock. A database-level lock (PostgreSQL
    row-level security) is planned as a second layer; see DECISIONS.md D-006.
    """

    def for_user(self, user):
        if user is None or not user.is_authenticated or not user.is_active:
            return self.none()
        if user.is_superuser:
            return self
        return self.filter(branch_id__in=user.accessible_branch_ids())


class BranchOwnedModel(TimeStampedModel):
    """A record that belongs to exactly one branch (students, sections, ...)."""

    branch = models.ForeignKey(
        "organisation.Branch", on_delete=models.PROTECT, related_name="+", verbose_name=_("branch")
    )

    objects = BranchScopedQuerySet.as_manager()

    class Meta:
        abstract = True


class AuditEvent(models.Model):
    """Append-only record of who changed what. Never edited or deleted by the app."""

    class Action(models.TextChoices):
        CREATE = "create", _("Created")
        UPDATE = "update", _("Updated")
        DELETE = "delete", _("Deleted")
        LOGIN = "login", _("Logged in")
        LOGIN_FAILED = "login_failed", _("Login failed")
        LOGOUT = "logout", _("Logged out")

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    model_label = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    branch_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["model_label", "object_id"])]
        # Deleting records made by mistake (apps/core/deletion.py); every deletion is recorded here.
        permissions = [("delete_records", "Can delete records made by mistake")]

    def __str__(self):
        return f"{self.occurred_at:%Y-%m-%d %H:%M} {self.action} {self.model_label}#{self.object_id}"
