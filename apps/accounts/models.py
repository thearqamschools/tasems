"""Users, roles and scoped role assignments.

A user's access = the roles they hold × the scope each role is held at.
Example: "Principal" at branch Samanabad, or "Regional Director" at region X.
Scopes, from widest to narrowest: network → head office → region → branch.
"""

from django.contrib.auth.models import AbstractUser, Permission
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import TimeStampedModel


class Scope(models.TextChoices):
    NETWORK = "network", _("Whole network")
    HEAD_OFFICE = "head_office", _("Head office")
    REGION = "region", _("Region")
    BRANCH = "branch", _("Branch")


@audited
class User(AbstractUser):
    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        URDU = "ur", "اردو"

    full_name_ur = models.CharField(_("full name (Urdu)"), max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    preferred_language = models.CharField(max_length=2, choices=Language.choices, default=Language.ENGLISH)

    # --- Scope helpers -----------------------------------------------------
    def active_assignments(self):
        today = timezone.localdate()
        return (
            self.role_assignments.filter(is_active=True)
            .filter(Q(starts_on__isnull=True) | Q(starts_on__lte=today))
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
            .select_related("role")
        )

    def accessible_branch_ids(self, permission=None):
        """IDs of branches this user may see. With `permission` ('app.codename'),
        only scopes whose role carries that permission count."""
        from apps.organisation.models import Branch

        if not self.is_active:
            return set()
        if self.is_superuser:
            return set(Branch.objects.values_list("id", flat=True))

        cache = self.__dict__.setdefault("_branch_scope_cache", {})
        if permission in cache:
            return cache[permission]

        assignments = self.active_assignments()
        if permission:
            app_label, codename = permission.split(".", 1)
            assignments = assignments.filter(
                role__permissions__content_type__app_label=app_label, role__permissions__codename=codename
            )

        ids = set()
        branches = Branch.objects.all()
        for a in assignments.distinct():
            if a.scope == Scope.NETWORK:
                ids |= set(branches.values_list("id", flat=True))
            elif a.scope == Scope.HEAD_OFFICE:
                ids |= set(branches.filter(head_office_id=a.head_office_id).values_list("id", flat=True))
            elif a.scope == Scope.REGION:
                ids |= set(branches.filter(region_id=a.region_id).values_list("id", flat=True))
            elif a.scope == Scope.BRANCH:
                ids.add(a.branch_id)
        cache[permission] = ids
        return ids

    @property
    def requires_mfa(self):
        """Superusers and anyone holding a privileged role must use two-factor login."""
        if self.is_superuser:
            return True
        return self.active_assignments().filter(role__requires_mfa=True).exists()

    def has_branch_perm(self, permission, branch_id):
        """True if the user holds `permission` through a role that covers this branch."""
        if self.is_superuser and self.is_active:
            return True
        return branch_id in self.accessible_branch_ids(permission)


@audited
class Role(TimeStampedModel):
    """A named bundle of permissions, e.g. Principal, Class Teacher, Accountant."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    name_ur = models.CharField(_("name (Urdu)"), max_length=100, blank=True)
    description = models.TextField(blank=True)
    allowed_scopes = models.JSONField(
        default=list, help_text=_("Scopes this role may be assigned at, e.g. ['branch'].")
    )
    permissions = models.ManyToManyField(Permission, blank=True, related_name="tasems_roles")
    requires_mfa = models.BooleanField(
        default=False, help_text=_("Privileged roles must use two-factor login (enforced from Milestone 1b).")
    )
    is_system = models.BooleanField(default=False, help_text=_("Created by TASEMS; edit with care."))

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@audited
class RoleAssignment(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    scope = models.CharField(max_length=20, choices=Scope.choices)
    head_office = models.ForeignKey(
        "organisation.HeadOffice", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    region = models.ForeignKey("organisation.Region", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    branch = models.ForeignKey("organisation.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Exactly the target that matches the scope must be filled in.
            models.CheckConstraint(
                name="assignment_scope_target_matches",
                condition=(
                    Q(scope="network", head_office__isnull=True, region__isnull=True, branch__isnull=True)
                    | Q(scope="head_office", head_office__isnull=False, region__isnull=True, branch__isnull=True)
                    | Q(scope="region", head_office__isnull=True, region__isnull=False, branch__isnull=True)
                    | Q(scope="branch", head_office__isnull=True, region__isnull=True, branch__isnull=False)
                ),
            ),
        ]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self):
        target = self.branch or self.region or self.head_office or _("Whole network")
        return f"{self.user} — {self.role} @ {target}"

    def clean(self):
        if self.role_id and self.role.allowed_scopes and self.scope not in self.role.allowed_scopes:
            raise ValidationError({"scope": _("This role cannot be assigned at this scope.")})
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": _("End date is before start date.")})


class MFADevice(TimeStampedModel):
    """Authenticator-app (TOTP) key for two-factor login. The key is stored encrypted."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mfa_device")
    secret_encrypted = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_step = models.BigIntegerField(default=0, help_text=_("Stops the same code being used twice."))

    def __str__(self):
        return f"Two-factor device for {self.user}"


class RecoveryCode(models.Model):
    """One-time backup codes for when the phone is lost. Only a hash is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=128)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Backup code for {self.user} ({'used' if self.used_at else 'unused'})"
