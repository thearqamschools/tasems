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
        MIDDLE = "middle", _("Middle School")
        HIGH = "high", _("High School / Matric")
        HIFZ = "hifz", _("Hifz-e-Quran")

    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=60)
    name_ur = models.CharField(_("name (Urdu)"), max_length=60, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices)
    sort_order = models.PositiveSmallIntegerField(unique=True)
    separate_by_gender = models.BooleanField(
        default=False, help_text=_("Boys and girls study in separate campuses/sections from this class onwards.")
    )
    attends_on_saturday = models.BooleanField(
        default=False, help_text=_("This class comes to school on Saturdays, so attendance is taken that day.")
    )
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
    class GenderGroup(models.TextChoices):
        MIXED = "mixed", _("Boys and Girls")
        BOYS = "boys", _("Boys")
        GIRLS = "girls", _("Girls")

    session = models.ForeignKey("organisation.AcademicSession", on_delete=models.PROTECT, related_name="sections")
    class_level = models.ForeignKey(ClassLevel, on_delete=models.PROTECT, related_name="sections")
    name = models.CharField(max_length=20, help_text=_("Usually Rose, Jasmine, Daisy, Pansy or Tulip"))
    gender_group = models.CharField(max_length=10, choices=GenderGroup.choices, default=GenderGroup.MIXED)
    # Required on the form (project lead, 28 Oct 2026); empty only on sections made before that.
    campus = models.ForeignKey(
        "organisation.Campus",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sections",
        help_text=_(
            "Building where this section studies. Usually Play Group to Class 5 (boys and girls) study in the girls "
            "campus; after that boys study in the boys campus and girls in the girls campus."
        ),
    )
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
        if self.campus_id and self.branch_id:
            if self.campus.branch_id != self.branch_id:
                raise ValidationError({"campus": _("Campus belongs to a different branch.")})
            # Boys and girls sections may study in a girls or boys campus (e.g. Play Group to Class 5 in the girls
            # campus); a boys-only section cannot be in a girls campus, and the other way round.
            if (
                "mixed" not in (self.campus.gender_group, self.gender_group)
                and self.gender_group != self.campus.gender_group
            ):
                raise ValidationError(
                    {"campus": _("This campus is for %(g)s only.") % {"g": self.campus.get_gender_group_display()}}
                )
        if self.class_level_id and self.class_level.separate_by_gender and self.gender_group == self.GenderGroup.MIXED:
            raise ValidationError({"gender_group": _("From this class onwards, sections are for boys or girls only.")})
        if self.class_teacher_id and self.branch_id:
            if self.branch_id not in self.class_teacher.accessible_branch_ids():
                raise ValidationError({"class_teacher": _("This teacher is not assigned to this branch.")})


# --- Subject teachers and timetable (M7) ------------------------------------------------------

WEEKDAYS = [
    (0, _("Monday")),
    (1, _("Tuesday")),
    (2, _("Wednesday")),
    (3, _("Thursday")),
    (4, _("Friday")),
    (5, _("Saturday")),
]


@audited
class SectionSubject(BranchOwnedModel):
    """Who teaches a subject to a section this session."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="subject_teachers")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="subject_sections"
    )

    class Meta:
        ordering = ["section", "subject__name"]
        constraints = [models.UniqueConstraint(fields=["section", "subject"], name="one_teacher_per_section_subject")]

    def __str__(self):
        return f"{self.section} {self.subject}: {self.teacher or '—'}"


@audited
class Period(BranchOwnedModel):
    """The branch's bell times: period 1, 2, … and breaks. The same for every class of the branch."""

    number = models.PositiveSmallIntegerField(help_text=_("Order in the day: 1, 2, 3 …"))
    label = models.CharField(max_length=30, blank=True, help_text=_("e.g. Break, Assembly. Empty for a period."))
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    is_break = models.BooleanField(default=False)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["branch", "number"], name="unique_period_number")]

    def __str__(self):
        name = self.label or _("Period %(n)s") % {"n": self.number}
        return f"{name} ({self.starts_at:%H:%M}–{self.ends_at:%H:%M})"

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": _("The period must end after it starts.")})


@audited
class TimetableEntry(BranchOwnedModel):
    """One cell of a class timetable: this section has this subject in this period on this day.
    The teacher is the section's teacher for that subject (SectionSubject)."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="timetable")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="entries")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["weekday", "period__number"]
        constraints = [
            models.UniqueConstraint(fields=["section", "weekday", "period"], name="one_subject_per_section_slot")
        ]

    def __str__(self):
        return f"{self.section} {self.get_weekday_display()} {self.period.number}: {self.subject}"
