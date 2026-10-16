"""Daily student attendance: marked once a day, per section.

AttendanceRecord: one row per student per day (about 50 million rows a year at
national scale; indexed by branch/date and section/date, ready for partitioning).
SectionAttendance: one row per section per day, saying the register was taken,
by whom, and the totals — this is what principals and head office look at.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel


class Status(models.TextChoices):
    PRESENT = "present", _("Present")
    ABSENT = "absent", _("Absent")
    LEAVE = "leave", _("Leave")
    LATE = "late", _("Late")


class AttendanceRecord(BranchOwnedModel):
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="attendance")
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, related_name="attendance")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    note = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "date"], name="one_attendance_per_student_per_day")]
        indexes = [
            models.Index(fields=["branch", "date", "status"]),
            models.Index(fields=["section", "date"]),
        ]

    def __str__(self):
        return f"{self.student} {self.date} {self.status}"


@audited
class SectionAttendance(BranchOwnedModel):
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, related_name="registers")
    date = models.DateField()
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    present = models.PositiveSmallIntegerField(default=0)
    absent = models.PositiveSmallIntegerField(default=0)
    leave = models.PositiveSmallIntegerField(default=0)
    late = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["section", "date"], name="one_register_per_section_per_day")]
        indexes = [models.Index(fields=["branch", "date"])]

    def __str__(self):
        return f"{self.section} {self.date}"

    @property
    def total(self):
        return self.present + self.absent + self.leave + self.late

    @property
    def attended(self):
        """Present and late both count as attending."""
        return self.present + self.late
