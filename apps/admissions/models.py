"""Admission inquiries and their follow-ups (DECISIONS D-048).

Every inquiry — walk-in, phone call, WhatsApp, Facebook, website, referral — is one record that
moves through: New → Contacted → Visit booked → Visited → Assessment → Offered → Admitted, or
Lost (with a reason). Each call, message, visit or note is a follow-up on its timeline, and the
next follow-up date makes sure no family is forgotten. An admitted inquiry is linked to the
student record it became.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel


class Source(models.TextChoices):
    WALK_IN = "walk_in", _("Walk-in")
    PHONE = "phone", _("Phone call")
    WHATSAPP = "whatsapp", _("WhatsApp")
    FACEBOOK = "facebook", _("Facebook")
    WEBSITE = "website", _("Website")
    REFERRAL = "referral", _("Referred by a parent")
    BANNER = "banner", _("Banner / flex / pamphlet")
    EVENT = "event", _("School event")
    OTHER = "other", _("Other")


@audited
class Inquiry(BranchOwnedModel):
    class Status(models.TextChoices):
        NEW = "new", _("New")
        CONTACTED = "contacted", _("Contacted")
        VISIT = "visit", _("Visit booked")
        VISITED = "visited", _("Visited")
        ASSESSMENT = "assessment", _("Assessment / interview")
        OFFERED = "offered", _("Seat offered")
        ADMITTED = "admitted", _("Admitted")
        LOST = "lost", _("Not joining")

    class LostReason(models.TextChoices):
        FEE = "fee", _("Fee too high")
        DISTANCE = "distance", _("Too far / transport")
        OTHER_SCHOOL = "other_school", _("Chose another school")
        NO_SEAT = "no_seat", _("No seat in the class")
        NO_RESPONSE = "no_response", _("No response")
        NOT_READY = "not_ready", _("Child not ready / too young")
        OTHER = "other", _("Other")

    OPEN = [Status.NEW, Status.CONTACTED, Status.VISIT, Status.VISITED, Status.ASSESSMENT, Status.OFFERED]

    child_name = models.CharField(_("child's name"), max_length=150)
    gender = models.CharField(max_length=10, choices=[("male", _("Boy")), ("female", _("Girl"))])
    date_of_birth = models.DateField(null=True, blank=True)
    class_level = models.ForeignKey(
        "academics.ClassLevel", on_delete=models.PROTECT, related_name="+", verbose_name=_("class applying for")
    )
    is_hifz = models.BooleanField(_("interested in Hifz"), default=False)
    parent_name = models.CharField(_("parent's name"), max_length=150)
    phone = models.CharField(_("mobile"), max_length=11, db_index=True)
    alt_phone = models.CharField(_("other phone"), max_length=20, blank=True)
    area = models.CharField(_("area / address"), max_length=200, blank=True)
    current_school = models.CharField(max_length=150, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices)
    referred_by = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    lost_reason = models.CharField(max_length=14, choices=LostReason.choices, blank=True)
    visit_at = models.DateTimeField(_("campus visit"), null=True, blank=True)
    next_follow_up = models.DateField(null=True, blank=True, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    student = models.OneToOneField(
        "people.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="inquiry"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    closed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "inquiries"
        indexes = [models.Index(fields=["branch", "status", "next_follow_up"])]

    def __str__(self):
        return f"{self.child_name} ({self.class_level}) — {self.parent_name}"

    @property
    def is_open(self):
        return self.status in self.OPEN


class FollowUp(BranchOwnedModel):
    class Kind(models.TextChoices):
        CALL = "call", _("Phone call")
        WHATSAPP = "whatsapp", _("WhatsApp message")
        VISIT = "visit", _("Campus visit")
        ASSESSMENT = "assessment", _("Assessment / interview")
        NOTE = "note", _("Note")
        STATUS = "status", _("Status change")

    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="follow_ups")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    note = models.TextField(blank=True)
    at = models.DateTimeField()
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-at", "-pk"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.inquiry}"
