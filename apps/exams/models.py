"""Examinations, marks and the result pattern.

Approved pattern (16 Oct 2026, DECISIONS D-030). Every subject is out of 100:

    Final exam 50 · Mid-Term exam 25 · Attendance 5 (automatic) · Discipline 5
    Neatness 5 · Summer vacation work 5 · Class work & homework 5

Exam papers are marked out of their own totals and converted to their share
(e.g. 60/80 in the Final = 37.5 of 50). Attendance and discipline belong to the
student and count the same in every subject; the other ratings are per subject.
A student passes a subject with 33% overall AND 33% of the exam marks, so
non-exam marks cannot carry a failed paper. Everything here is data that head
office can change in Setup.
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
        {"grade": "A+", "min": 80},
        {"grade": "A", "min": 70},
        {"grade": "B", "min": 60},
        {"grade": "C", "min": 50},
        {"grade": "D", "min": 40},
        {"grade": "E", "min": 33},
        {"grade": "F", "min": 0},
    ]


def default_attendance_points():
    # [minimum attendance %, points out of the component's maximum]
    return [[95, 5], [90, 4], [85, 3], [80, 2], [75, 1], [0, 0]]


@audited
class GradingScheme(TimeStampedModel):
    class Positions(models.TextChoices):
        NONE = "none", _("Do not show positions")
        TOP3 = "top3", _("Show 1st, 2nd and 3rd only")
        ALL = "all", _("Show every student's position")

    class AbsentMid(models.TextChoices):
        ZERO = "zero", _("Any absence in the Mid-Term counts as zero")
        FINAL_COVERS = "final_covers", _("Absence with leave: the Final covers the Mid-Term's share")

    name = models.CharField(max_length=80, unique=True)
    stages = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Stages this scheme applies to, e.g. ['early_years']. Empty with 'default' = all others."),
    )
    pass_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=33, validators=PERCENT, help_text=_("Of the subject total")
    )
    exam_pass_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=33, validators=PERCENT, help_text=_("Of the exam marks alone")
    )
    bands = models.JSONField(default=default_bands)
    attendance_points = models.JSONField(default=default_attendance_points)
    positions = models.CharField(max_length=10, choices=Positions.choices, default=Positions.TOP3)
    absent_mid_rule = models.CharField(max_length=14, choices=AbsentMid.choices, default=AbsentMid.FINAL_COVERS)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["is_default"], condition=Q(is_default=True), name="one_default_scheme")
        ]

    def __str__(self):
        return self.name

    @classmethod
    def for_stage(cls, stage):
        for scheme in cls.objects.exclude(is_default=True):
            if stage in (scheme.stages or []):
                return scheme
        return cls.objects.filter(is_default=True).first()

    @property
    def total(self):
        return sum(c.max_marks for c in self.components.all())


@audited
class GradingComponent(TimeStampedModel):
    class Source(models.TextChoices):
        FINAL = "final", _("Final exam paper")
        MID = "mid", _("Mid-Term exam paper")
        ATTENDANCE = "attendance", _("Attendance (automatic)")
        RATING = "rating", _("Teacher's rating")

    class Scope(models.TextChoices):
        SUBJECT = "subject", _("Per subject")
        STUDENT = "student", _("Same for all subjects")

    scheme = models.ForeignKey(GradingScheme, on_delete=models.CASCADE, related_name="components")
    code = models.SlugField(max_length=30)
    name = models.CharField(max_length=60)
    name_ur = models.CharField(_("name (Urdu)"), max_length=60, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.SUBJECT)
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.5"))])
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        constraints = [models.UniqueConstraint(fields=["scheme", "code"], name="unique_component_code")]

    def __str__(self):
        return f"{self.name} ({self.max_marks})"

    def clean(self):
        if self.source in (self.Source.FINAL, self.Source.MID) and self.scope != self.Scope.SUBJECT:
            raise ValidationError(_("Exam papers are always per subject."))
        if self.source == self.Source.ATTENDANCE and self.scope != self.Scope.STUDENT:
            raise ValidationError(_("Attendance belongs to the student, not to a subject."))

    @property
    def is_exam(self):
        return self.source in (self.Source.FINAL, self.Source.MID)


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


class Rating(BranchOwnedModel):
    """A teacher's marks for a non-exam component (discipline, neatness, summer work, class work).
    `subject` is empty for components that belong to the student (e.g. discipline)."""

    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="ratings")
    session = models.ForeignKey("organisation.AcademicSession", on_delete=models.PROTECT, related_name="+")
    component = models.ForeignKey(GradingComponent, on_delete=models.PROTECT, related_name="ratings")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    value = models.DecimalField(max_digits=5, decimal_places=2)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "session", "component", "subject"],
                name="one_rating_per_subject",
                nulls_distinct=False,
            )
        ]
        indexes = [models.Index(fields=["branch", "session", "component"])]

    def __str__(self):
        return f"{self.student} {self.component} {self.subject or ''}: {self.value}"


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
