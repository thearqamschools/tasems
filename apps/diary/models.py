"""Daily Diary ("Daily Learning Overview"), modelled on The Arqam Schools' current diary.

One diary per section per school day. Each subject can have an In Class Learning
entry, a Home Learning Task (with a deadline), or both. Subjects with nothing in a
part of the diary are left out of that part when the diary is printed or shared.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel


@audited
class DiaryLayout(TimeStampedModel):
    """Network-wide diary design, set by head office. Only one row is used."""

    title = models.CharField(max_length=100, default="Daily Learning Overview")
    title_ur = models.CharField(_("title (Urdu)"), max_length=100, blank=True)
    left_logo = models.FileField(
        upload_to="branding/", blank=True, help_text=_("Official logo file (PNG or SVG). Never redrawn or recoloured.")
    )
    right_logo = models.FileField(upload_to="branding/", blank=True)
    header_colour = models.CharField(max_length=7, default="#cdbfe4", help_text=_("Table heading colour, e.g. #cdbfe4"))
    footer_text = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.title

    @classmethod
    def current(cls):
        return cls.objects.order_by("pk").first() or cls()


@audited
class DiaryWeek(TimeStampedModel):
    """Theme of the week, week number and quote. Leave branch empty for the whole network;
    a branch's own entry for the same week takes priority."""

    branch = models.ForeignKey("organisation.Branch", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    starts_on = models.DateField(help_text=_("Monday of the week"))
    week_number = models.PositiveSmallIntegerField(null=True, blank=True)
    theme = models.CharField(_("theme of the week"), max_length=120, blank=True)
    theme_ur = models.CharField(_("theme of the week (Urdu)"), max_length=120, blank=True)
    quote = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "starts_on"], name="one_week_entry_per_branch"),
            models.UniqueConstraint(
                fields=["starts_on"], condition=Q(branch__isnull=True), name="one_network_week_entry"
            ),
        ]

    def __str__(self):
        return f"{self.starts_on} {self.theme}"


@audited
class Diary(BranchOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")

    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, related_name="diaries")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    written_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["section", "date"], name="one_diary_per_section_per_day")]
        indexes = [models.Index(fields=["branch", "date"])]
        verbose_name_plural = "diaries"

    def __str__(self):
        return f"{self.section} {self.date}"


class DiaryEntry(models.Model):
    diary = models.ForeignKey(Diary, on_delete=models.CASCADE, related_name="entries")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="+")
    sort_order = models.PositiveSmallIntegerField(default=0)
    in_class = models.TextField(_("in class learning"), blank=True)
    home_task = models.TextField(_("home learning task"), blank=True)
    deadline = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "subject__name"]
        constraints = [models.UniqueConstraint(fields=["diary", "subject"], name="one_entry_per_subject")]
        verbose_name_plural = "diary entries"

    def __str__(self):
        return f"{self.diary} — {self.subject}"
