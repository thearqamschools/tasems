"""Academic structure.

Network-wide (set by head office): class levels and subjects — The Arqam Schools
uses one syllabus across Pakistan.
Branch-owned: sections for each session (e.g. Class 5-A at Samanabad, 2026-27).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel


@audited
class ClassLevel(TimeStampedModel):
    class Stage(models.TextChoices):
        EARLY_YEARS = "early_years", _("Early Years")
        PRIMARY = "primary", _("Primary")
        MIDDLE = "middle", _("Middle")
        SECONDARY = "secondary", _("Secondary / Matric")
        HIFZ = "hifz", _("Hifz-e-Quran")

    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=60)
    name_ur = models.CharField(_("name (Urdu)"), max_length=60, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices)
    sort_order = models.PositiveSmallIntegerField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


@audited
class Subject(TimeStampedModel):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    name_ur = models.CharField(_("name (Urdu)"), max_length=80, blank=True)
    is_rtl = models.BooleanField(
        default=False, help_text=_("Content is written right-to-left (Urdu, Islamiat, Arabic, Nazra).")
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@audited
class CurriculumSubject(TimeStampedModel):
    """Which subjects are taught in which class (network-wide)."""

    class_level = models.ForeignKey(ClassLevel, on_delete=models.PROTECT, related_name="curriculum")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="curriculum")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["class_level__sort_order", "sort_order"]
        constraints = [models.UniqueConstraint(fields=["class_level", "subject"], name="unique_subject_per_class")]

    def __str__(self):
        return f"{self.class_level} — {self.subject}"


@audited
class Section(BranchOwnedModel):
    session = models.ForeignKey("organisation.AcademicSession", on_delete=models.PROTECT, related_name="sections")
    class_level = models.ForeignKey(ClassLevel, on_delete=models.PROTECT, related_name="sections")
    name = models.CharField(max_length=20, help_text=_("e.g. A, B, Rose, Jasmine"))
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="class_sections"
    )
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["class_level__sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "session", "class_level", "name"], name="unique_section")
        ]
        indexes = [models.Index(fields=["branch", "session"])]

    def __str__(self):
        return f"{self.class_level}-{self.name}"

    def clean(self):
        if self.class_teacher_id and self.branch_id:
            if self.branch_id not in self.class_teacher.accessible_branch_ids():
                raise ValidationError({"class_teacher": _("This teacher is not assigned to this branch.")})
