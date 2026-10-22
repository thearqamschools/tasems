"""Notices (circulars) for parents and staff, and message templates for parents (M8)."""

import secrets
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import TimeStampedModel


def notice_file_path(notice, filename):
    return f"private/notices/{secrets.token_hex(16)}{Path(filename).suffix.lower()}"


class NoticeQuerySet(models.QuerySet):
    def for_branch(self, branch):
        """Notices that reach this branch: its own, its head office's and the whole network's."""
        return self.filter(
            Q(branch=branch)
            | Q(branch__isnull=True, head_office_id=branch.head_office_id)
            | Q(branch__isnull=True, head_office__isnull=True)
        )

    def live(self, today):
        return self.filter(is_withdrawn=False, publish_on__lte=today).filter(
            Q(expires_on__isnull=True) | Q(expires_on__gte=today)
        )


@audited
class Notice(TimeStampedModel):
    """A circular. Where: one branch, every branch of a head office, or the whole network (both empty)."""

    class Audience(models.TextChoices):
        PARENTS = "parents", _("Parents")
        STAFF = "staff", _("Staff")
        EVERYONE = "everyone", _("Parents and staff")

    branch = models.ForeignKey("organisation.Branch", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    head_office = models.ForeignKey(
        "organisation.HeadOffice", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("notice"), max_length=4000)
    audience = models.CharField(_("for"), max_length=10, choices=Audience.choices, default=Audience.PARENTS)
    class_levels = models.ManyToManyField(
        "academics.ClassLevel",
        blank=True,
        related_name="+",
        verbose_name=_("classes"),
        help_text=_("Only the parents of these classes. Leave empty for all classes."),
    )
    publish_on = models.DateField(_("show from"))
    expires_on = models.DateField(_("show until"), null=True, blank=True)
    attachment = models.FileField(_("attachment"), upload_to=notice_file_path, blank=True)
    is_withdrawn = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    objects = NoticeQuerySet.as_manager()

    class Meta:
        ordering = ["-publish_on", "-pk"]
        permissions = [("send_messages", "Can prepare messages to parents")]

    def __str__(self):
        return self.title

    @property
    def for_parents(self):
        return self.audience in (self.Audience.PARENTS, self.Audience.EVERYONE)

    @property
    def for_staff(self):
        return self.audience in (self.Audience.STAFF, self.Audience.EVERYONE)


class NoticeRead(models.Model):
    """Who has opened a notice (parents and staff), so the sender sees how many read it."""

    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["notice", "user"], name="one_read_per_person")]

    def __str__(self):
        return f"{self.user} read {self.notice}"


@audited
class MessageTemplate(TimeStampedModel):
    """A message to parents with placeholders, e.g. {student} {amount_due}. Network-wide; head office edits."""

    name = models.CharField(_("name"), max_length=80)
    body = models.TextField(_("message"), max_length=1000)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MessageBatch(models.Model):
    """A list of messages prepared for parents (for WhatsApp or a bulk SMS tool), kept as a record."""

    branch = models.ForeignKey("organisation.Branch", on_delete=models.CASCADE, related_name="+")
    template = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL, null=True, related_name="+")
    audience = models.CharField(max_length=40)
    count = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.count} messages ({self.audience}) {self.created_at:%d %b %Y}"
