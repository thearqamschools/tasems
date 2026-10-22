"""Students, guardians and yearly enrolments.

A student is stored once. Each academic session gets one Enrolment that places
the student in a section, so history is kept year to year. Students have no
logins; guardians (parents) will get portal logins in a later phase.
"""

import secrets

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, BranchScopedQuerySet, TimeStampedModel


class Gender(models.TextChoices):
    MALE = "male", _("Male")
    FEMALE = "female", _("Female")


@audited
class Guardian(BranchOwnedModel):
    full_name = models.CharField(max_length=150)
    full_name_ur = models.CharField(_("full name (Urdu)"), max_length=150, blank=True)
    phone = models.CharField(max_length=20, db_index=True, help_text=_("Primary mobile / WhatsApp number"))
    alt_phone = models.CharField(max_length=20, blank=True)
    cnic = models.CharField(_("CNIC"), max_length=15, blank=True)
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    organisation = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


def photo_path(student, filename):
    """Private folder and a random name; shown only through TASEMS to staff of the branch."""
    return f"private/student-photos/{student.branch_id}/{secrets.token_hex(16)}.jpg"


@audited
class Student(BranchOwnedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        WITHDRAWN = "withdrawn", _("Withdrawn / Left")
        TRANSFERRED = "transferred", _("Transferred out")
        GRADUATED = "graduated", _("Graduated")

    class SubjectGroup(models.TextChoices):
        BIOLOGY = "biology", _("Biology")
        COMPUTER = "computer", _("Computer")

    admission_no = models.CharField(max_length=30)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    full_name_ur = models.CharField(_("full name (Urdu)"), max_length=150, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    b_form_no = models.CharField(_("B-Form number"), max_length=15, blank=True)
    father_name = models.CharField(_("father's name"), max_length=150, blank=True)
    father_cnic = models.CharField(
        _("father's CNIC"),
        max_length=13,
        blank=True,
        db_index=True,
        help_text=_("13 digits. Brothers and sisters are recognised by this number for the sibling fee."),
    )
    email = models.EmailField(blank=True)
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    subject_group = models.CharField(
        max_length=10, choices=SubjectGroup.choices, blank=True, help_text=_("Pre-9th, 9th and 10th only.")
    )
    reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_path, blank=True)
    admission_date = models.DateField()
    is_hifz = models.BooleanField(_("Hifz student"), default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    status_changed_on = models.DateField(null=True, blank=True)
    guardians = models.ManyToManyField(Guardian, through="StudentGuardian", related_name="students")

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "admission_no"], name="unique_admission_no_per_branch")
        ]
        indexes = [models.Index(fields=["branch", "status"])]

    def __str__(self):
        return f"{self.full_name} [{self.admission_no}]"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def siblings(self):
        """Brothers and sisters in this branch: the same father's CNIC (the rule used for the sibling fee)."""
        if not self.father_cnic:
            return Student.objects.none()
        return Student.objects.filter(branch_id=self.branch_id, father_cnic=self.father_cnic).exclude(pk=self.pk)


class StudentLinkQuerySet(BranchScopedQuerySet):
    def for_user(self, user):
        if user is None or not user.is_authenticated or not user.is_active:
            return self.none()
        if user.is_superuser:
            return self
        return self.filter(student__branch_id__in=user.accessible_branch_ids())


@audited
class StudentGuardian(TimeStampedModel):
    class Relationship(models.TextChoices):
        FATHER = "father", _("Father")
        MOTHER = "mother", _("Mother")
        GUARDIAN = "guardian", _("Guardian")
        OTHER = "other", _("Other")

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardian_links")
    guardian = models.ForeignKey(Guardian, on_delete=models.PROTECT, related_name="student_links")
    relationship = models.CharField(max_length=20, choices=Relationship.choices)
    relation_detail = models.CharField(
        max_length=60, blank=True, help_text=_("For a guardian, e.g. uncle, aunt, grandfather.")
    )
    is_primary_contact = models.BooleanField(default=False)

    objects = StudentLinkQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "guardian"], name="unique_student_guardian"),
            models.UniqueConstraint(
                fields=["student"], condition=models.Q(is_primary_contact=True), name="one_primary_contact"
            ),
        ]

    def __str__(self):
        return f"{self.guardian.full_name} → {self.student.full_name} ({self.get_relationship_display()})"

    def clean(self):
        if self.student_id and self.guardian_id and self.student.branch_id != self.guardian.branch_id:
            raise ValidationError(_("Guardian and student must belong to the same branch."))


@audited
class Enrolment(BranchOwnedModel):
    """Places a student in a section for one academic session."""

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrolments")
    session = models.ForeignKey("organisation.AcademicSession", on_delete=models.PROTECT, related_name="enrolments")
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, related_name="enrolments")
    roll_no = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["section", "roll_no"]
        constraints = [
            models.UniqueConstraint(fields=["student", "session"], name="one_enrolment_per_session"),
            models.UniqueConstraint(
                fields=["section", "roll_no"], condition=models.Q(roll_no__isnull=False), name="unique_roll_no"
            ),
        ]

    def __str__(self):
        return f"{self.student} — {self.section} ({self.session})"

    def clean(self):
        errors = {}
        if self.student_id and self.branch_id and self.student.branch_id != self.branch_id:
            errors["student"] = _("Student belongs to a different branch.")
        if self.section_id:
            if self.branch_id and self.section.branch_id != self.branch_id:
                errors["section"] = _("Section belongs to a different branch.")
            if self.session_id and self.section.session_id != self.session_id:
                errors["section"] = _("Section belongs to a different session.")
            group = self.section.gender_group
            if (
                self.student_id
                and group != "mixed"
                and {"boys": "male", "girls": "female"}[group] != self.student.gender
            ):
                errors["section"] = _("This section is for %(group)s only.") % {
                    "group": self.section.get_gender_group_display()
                }
        if errors:
            raise ValidationError(errors)


@audited
class Certificate(BranchOwnedModel):
    """A leaving or character certificate. Numbered per branch; reprints show the same number."""

    class Kind(models.TextChoices):
        LEAVING = "leaving", _("School leaving certificate")
        CHARACTER = "character", _("Character certificate")

    class Conduct(models.TextChoices):
        EXCELLENT = "excellent", _("Excellent")
        VERY_GOOD = "very_good", _("Very good")
        GOOD = "good", _("Good")
        SATISFACTORY = "satisfactory", _("Satisfactory")

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="certificates")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    number = models.PositiveIntegerField()
    reference = models.CharField(
        _("reference no."), max_length=60, blank=True, help_text=_("e.g. HO-FAISALABAD-FSD-0001; never repeated")
    )
    issued_on = models.DateField()
    conduct = models.CharField(max_length=15, choices=Conduct.choices, default=Conduct.GOOD)
    last_class = models.CharField(max_length=80, blank=True, help_text=_("Class and section at the time of leaving"))
    left_on = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    dues_cleared = models.BooleanField(default=True)
    remarks = models.CharField(max_length=200, blank=True)
    issued_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-issued_on", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "kind", "number"], name="unique_certificate_number"),
            models.UniqueConstraint(
                fields=["reference"], condition=~models.Q(reference=""), name="unique_certificate_reference"
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.reference or self.number} — {self.student}"
