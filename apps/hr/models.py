"""Staff records, staff attendance from the biometric machines, and leave.

Staff attendance (DECISIONS D-011, D-042):
* The face-recognition machines stay. Their export (punches: machine ID + date and time) is
  imported; each punch is kept as it came.
* Each working day becomes one StaffDay per employee: first time in, last time out and a status
  (present, late, half day, absent, on leave, holiday, off). Days are worked out again whenever
  punches, leave or settings change — except days a principal corrected by hand, which keep the
  correction (with its reason) until it is removed.
* Duty time, grace minutes and working days are per-branch settings; until duty time is set,
  anyone who punched in is simply "present".
"""

import datetime as dt
import secrets
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel

WEEKDAYS = [_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"), _("Friday"), _("Saturday"), _("Sunday")]


def default_working_days():
    return [0, 1, 2, 3, 4, 5]  # Monday–Saturday; Sunday off (to confirm for staff)


# Designations in order of seniority (project lead, 19 Oct 2026). Stored in English, shown translated.
DESIGNATIONS = [
    ("Director", _("Director")),
    ("Principal", _("Principal")),
    ("Vice Principal", _("Vice Principal")),
    ("Coordinator", _("Coordinator")),
    ("Accountant", _("Accountant")),
    ("Admin", _("Admin")),
    ("Senior Teacher", _("Senior Teacher")),
    ("Junior Teacher", _("Junior Teacher")),
    ("Qari", _("Qari")),
    ("Guard", _("Guard")),
    ("Aapa", _("Aapa")),
    ("Janitorial staff", _("Janitorial staff")),
    ("Office boy", _("Office boy")),
    ("Helping staff / Other", _("Helping staff / Other")),
    ("Lawyer", _("Lawyer")),
]


def cv_path(employee, filename):
    """Private folder and a random name, so a CV cannot be guessed; it is opened only through TASEMS."""
    extension = Path(filename).suffix.lower()
    return f"private/staff-cv/{employee.branch_id}/{secrets.token_hex(16)}{extension}"


@audited
class Employee(BranchOwnedModel):
    class StaffType(models.TextChoices):
        TEACHING = "teaching", _("Teacher")
        HIFZ = "hifz", _("Hifz teacher (Qari)")
        ADMIN = "admin", _("Administration / office")
        SUPPORT = "support", _("Support staff")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Working")
        RESIGNED = "resigned", _("Resigned")
        TERMINATED = "terminated", _("Services ended")
        RETIRED = "retired", _("Retired")

    code = models.CharField(_("employee code"), max_length=20)
    machine_id = models.CharField(
        _("biometric machine ID"),
        max_length=20,
        blank=True,
        help_text=_("The number this person is enrolled under on the attendance machine."),
    )
    full_name = models.CharField(max_length=150)
    full_name_ur = models.CharField(_("full name (Urdu)"), max_length=150, blank=True)
    father_name = models.CharField(_("father's name"), max_length=150, blank=True)
    husband_name = models.CharField(_("husband's name"), max_length=150, blank=True)
    gender = models.CharField(max_length=10, choices=[("male", _("Male")), ("female", _("Female"))])
    cnic = models.CharField(_("CNIC"), max_length=13, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(_("mobile"), max_length=11, blank=True)
    alt_phone = models.CharField(_("other phone"), max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(_("present address"), blank=True)
    permanent_address = models.TextField(blank=True)
    designation = models.CharField(
        max_length=80, help_text=_("Logins and what the person may do follow the designation.")
    )
    staff_type = models.CharField(max_length=10, choices=StaffType.choices)
    campus = models.ForeignKey("organisation.Campus", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    qualification = models.CharField(max_length=150, blank=True)
    joined_on = models.DateField(_("joining date"))
    left_on = models.DateField(_("leaving date"), null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee",
        help_text=_("The person's TASEMS login, if they have one."),
    )
    notes = models.TextField(blank=True)
    cv = models.FileField(_("CV"), upload_to=cv_path, blank=True, help_text=_("JPG, PNG or PDF, up to 5 MB."))

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "code"], name="unique_employee_code_per_branch"),
            models.UniqueConstraint(
                fields=["branch", "machine_id"], condition=~Q(machine_id=""), name="unique_machine_id_per_branch"
            ),
        ]
        indexes = [models.Index(fields=["branch", "status"])]

    def __str__(self):
        return f"{self.full_name} [{self.code}]"

    def clean(self):
        if self.left_on and self.joined_on and self.left_on < self.joined_on:
            raise ValidationError({"left_on": _("Leaving date is before the joining date.")})
        if self.status == self.Status.ACTIVE and self.left_on:
            raise ValidationError({"status": _("A person with a leaving date cannot be marked as working.")})
        if self.campus_id and self.branch_id and self.campus.branch_id != self.branch_id:
            raise ValidationError({"campus": _("Campus belongs to a different branch.")})

    def employed_on(self, date):
        return self.joined_on <= date and (self.left_on is None or date <= self.left_on)


@audited
class HRSettings(TimeStampedModel):
    """Duty time and working days for one branch (Advanced setup → HR settings)."""

    branch = models.OneToOneField("organisation.Branch", on_delete=models.CASCADE, related_name="hr_settings")
    duty_starts = models.TimeField(null=True, blank=True, help_text=_("e.g. 07:45. Empty: late is not worked out."))
    duty_ends = models.TimeField(null=True, blank=True)
    grace_minutes = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(120)], help_text=_("Minutes after duty time still counted on time.")
    )
    half_day_after = models.TimeField(
        null=True, blank=True, help_text=_("Arriving after this time counts as a half day. Empty: not used.")
    )
    working_days = models.JSONField(
        default=default_working_days, help_text=_("Weekday numbers, Monday = 0 … Sunday = 6.")
    )

    class Meta:
        verbose_name = "HR settings"
        verbose_name_plural = "HR settings"

    def __str__(self):
        return f"HR settings — {self.branch}"

    @classmethod
    def for_branch(cls, branch):
        return cls.objects.filter(branch=branch).first() or cls(branch=branch)


@audited
class Holiday(TimeStampedModel):
    """A day off for staff: for the whole network (branch empty) or one branch."""

    branch = models.ForeignKey("organisation.Branch", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "date"], name="one_holiday_per_day", nulls_distinct=False)
        ]

    def __str__(self):
        return f"{self.date:%d %b %Y} {self.name}"


@audited
class LeaveType(TimeStampedModel):
    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=60)
    name_ur = models.CharField(_("name (Urdu)"), max_length=60, blank=True)
    days_per_year = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text=_("Allowed days per academic session. Empty: no limit set.")
    )
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@audited
class LeaveRequest(BranchOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for approval")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Not approved")
        CANCELLED = "cancelled", _("Cancelled")

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="+")
    starts_on = models.DateField()
    ends_on = models.DateField()
    days = models.PositiveSmallIntegerField(default=0, help_text=_("Working days in the period"))
    reason = models.CharField(max_length=250)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-starts_on"]
        permissions = [("approve_leaverequest", "Can approve or reject leave")]

    def __str__(self):
        return f"{self.employee} — {self.leave_type} {self.starts_on:%d %b}–{self.ends_on:%d %b %Y}"

    def clean(self):
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": _("The last day is before the first day.")})
        if self.starts_on and self.ends_on and (self.ends_on - self.starts_on).days > 180:
            raise ValidationError({"ends_on": _("Leave longer than 180 days must be split.")})


class Punch(BranchOwnedModel):
    """One check-in or check-out from the attendance machine (or entered by hand)."""

    class Source(models.TextChoices):
        MACHINE = "machine", _("Attendance machine file")
        MANUAL = "manual", _("Entered by hand")

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="punches")
    at = models.DateTimeField()
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MACHINE)
    batch = models.CharField(max_length=40, blank=True, help_text=_("Which import it came from"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["at"]
        constraints = [models.UniqueConstraint(fields=["employee", "at"], name="one_punch_per_moment")]
        indexes = [models.Index(fields=["branch", "at"])]


class StaffDay(BranchOwnedModel):
    class Status(models.TextChoices):
        PRESENT = "present", _("Present")
        LATE = "late", _("Late")
        HALF_DAY = "half_day", _("Half day")
        ABSENT = "absent", _("Absent")
        LEAVE = "leave", _("On leave")
        HOLIDAY = "holiday", _("Holiday")
        OFF = "off", _("Off day")

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="days")
    date = models.DateField()
    first_in = models.TimeField(null=True, blank=True)
    last_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    leave = models.ForeignKey(LeaveRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    is_corrected = models.BooleanField(default=False, help_text=_("Set by hand; kept when days are worked out again"))
    note = models.CharField(max_length=200, blank=True)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="one_staff_day")]
        indexes = [models.Index(fields=["branch", "date", "status"])]

    def __str__(self):
        return f"{self.employee} {self.date}: {self.status}"

    CODES = {
        "present": "P",
        "late": "L",
        "half_day": "H",
        "absent": "A",
        "leave": "LV",
        "holiday": "HD",
        "off": "–",
    }

    @property
    def code(self):
        return self.CODES.get(self.status, "")

    @property
    def hours(self):
        if self.first_in and self.last_out and self.last_out > self.first_in:
            delta = dt.datetime.combine(self.date, self.last_out) - dt.datetime.combine(self.date, self.first_in)
            return round(delta.total_seconds() / 3600, 1)
        return None
