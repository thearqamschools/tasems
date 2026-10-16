"""Parent accounts (DECISIONS D-009, D-046).

A parent signs in with the mobile number the school has on record for them and a password
they choose. They see every active child linked to that mobile number — in any branch —
and nothing else. There is no SMS gateway: to set or reset a password the school gives the
parent a one-time access code (printed slip), valid for 14 days.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ParentAccount(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_account")
    phone = models.CharField(max_length=11, unique=True, help_text="03XXXXXXXXX")

    def __str__(self):
        return f"Parent {self.phone}"


class AccessCode(TimeStampedModel):
    """One-time code a parent uses to set (or reset) their password. Only a hash is kept."""

    phone = models.CharField(max_length=11, db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    branch = models.ForeignKey("organisation.Branch", on_delete=models.CASCADE, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Access code for {self.phone}"
