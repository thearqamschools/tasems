"""Examinations, marks and grading.

Grading (proposed default, DECISIONS D-030): each paper is marked out of its own total.
The annual result converts each exam to a percentage and combines them by weight:

    subject score (out of 100) = Mid-Term % × 30% + Final % × 70%

Class tests are recorded for progress but carry 0% weight by default. Weights, pass
mark, grade bands and position rules live in GradingScheme rows, so head office can
change them without code changes.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel

PERCENT = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))]


def default_bands():
    # Same bands as the Punjab boards use for Matric, so parents read them the same way.
    return [
        {"grade": "A+", "min": 80, "remark": "Outstanding"},
        {"grade": "A", "min": 70, "remark": "Excellent"},
        {"grade": "B", "min": 60, "remark": "Very good"},
        {"grade": "C", "min": 50, "remark": "Good"},
        {"grade": "D", "min": 40, "remark": "Fair"},
        {"grade": "E", "min": 33, "remark": "Satisfactory"},
        {"grade": "F", "min": 0, "remark": "Needs improvement"},
    ]


@audited
class GradingScheme(TimeStampedModel):
    class Positions(models.TextChoices):
        NONE = "none", _("Do not show positions")
        TOP3 = "top3", _("Show 1st, 2nd and 3rd only")
        ALL = "all", _("Show every student's position")

    class AbsentMid(models.TextChoices):
        ZERO = "zero", _("Absent in Mid-Term counts as zero")
        FINAL_ONLY = "final_only", _("Excused absence: Final counts for 100%")

    name = models.CharField(max_length=80, unique=True)
    stages = models.JSONField(
        default=list, help_text=_("Stages this scheme applies to, e.g. ['primary', 'middle']. Empty = all stages.")
    )
    test_weight = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=PERCENT)
    mid_weight = models.DecimalField(max_digits=5, decimal_places=2, default=30, validators=PERCENT)
    final_weight = models.DecimalField(max_digits=5, decimal_places=2, default=70, validators=PERCENT)
    pass_percent = models.DecimalField(max_digits=5, decimal_places=2, default=33, validators=PERCENT)
    bands = models.JSONField(default=default_bands)
    positions = models.CharField(max_length=10, choices=Positions.choices, default=Positions.TOP3)
    absent_mid_rule = models.CharField(max_length=12, choices=AbsentMid.choices, default=AbsentMid.FINAL_ONLY)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["is_default"], condition=Q(is_default=True), name="one_default_scheme")
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.test_weight + self.mid_weight + self.final_weight != 100:
            raise ValidationError(_("Test, Mid-Term and Final weights must add up to 100."))

    @classmethod
    def for_stage(cls, stage):
        for scheme in cls.objects.exclude(is_default=True):
            if stage in (scheme.stages or []):
                return scheme
        return cls.objects.filter(is_default=True).first() or cls(name="Default")


@audited
class Exam(TimeStampedModel):
    class Kind(models.TextChoices):
        TEST = "test", _("Class test")
        MID = "mid", _("Mid-Term")
        FINAL = "final", _("Final")

    session = models.ForeignKey("organisation.AcademicSession", on_delete=models.PROTECT, related_name="exams")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=120, help_text=_("e.g. Mid-Term Examination 2026-27"))
    name_ur = models.CharField(_("name (Urdu)"), max_length=120, blank=True)
    branch = models.ForeignKey(
        "organisation.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Leave empty for an exam held across the whole network."),
    )
    starts_on = models.DateField(null=True, blank=True)
    marks_due_on = models.DateField(
        null=True, blank=True, help_text=_("After this date only principals can change marks.")
    )
    is_published = models.BooleanField(default=False, help_text=_("Result cards can be shared with parents."))

    class Meta:
        ordering = ["-session__starts_on", "kind", "starts_on"]

    def __str__(self):
        return self.name


@audited
class Paper(TimeStampedModel):
    """One subject's paper for one class in an exam, with its own total marks."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="papers")
    class_level = models.ForeignKey("academics.ClassLevel", on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="+")
    total_marks = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["class_level__sort_order", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "class_level", "subject"], name="one_paper_per_subject_class")
        ]

    def __str__(self):
        return f"{self.exam} — {self.class_level} {self.subject} ({self.total_marks})"


class Mark(BranchOwnedModel):
    class Status(models.TextChoices):
        PRESENT = "present", _("Present")
        ABSENT = "absent", _("Absent")
        EXCUSED = "excused", _("Absent with leave")

    paper = models.ForeignKey(Paper, on_delete=models.PROTECT, related_name="marks")
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="marks")
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, related_name="+")
    obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["paper", "student"], name="one_mark_per_paper_student"),
            models.CheckConstraint(
                condition=Q(status="present", obtained__isnull=False) | ~Q(status="present"),
                name="present_needs_marks",
            ),
        ]
        indexes = [models.Index(fields=["section", "paper"])]

    def __str__(self):
        return f"{self.student} {self.paper}: {self.obtained}"


@audited
class ResultRemark(BranchOwnedModel):
    student = models.ForeignKey("people.Student", on_delete=models.CASCADE, related_name="result_remarks")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="+")
    teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "exam"], name="one_remark_per_student_exam")]

    def __str__(self):
        return f"{self.student} {self.exam}"
