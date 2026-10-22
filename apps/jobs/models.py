import secrets

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BranchOwnedModel


def job_file_path(job, filename):
    """Private folder and a random name; the file is opened only through TASEMS by the person who asked."""
    return f"private/print-jobs/{job.branch_id}/{secrets.token_hex(16)}.pdf"


class Job(BranchOwnedModel):
    """A large PDF made in the background (M6, D-074): the page shows progress and a download link."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("Waiting")
        RUNNING = "running", _("Being made")
        DONE = "done", _("Ready")
        FAILED = "failed", _("Could not be made")

    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True)
    done = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to=job_file_path, blank=True)
    error = models.CharField(max_length=300, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def percent(self):
        return round(100 * self.done / self.total) if self.total else 0

    @property
    def finished(self):
        return self.status in (self.Status.DONE, self.Status.FAILED)
