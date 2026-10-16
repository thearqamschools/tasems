"""Organisation structure: head offices → regions → branches, plus academic sessions."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import TimeStampedModel


@audited
class HeadOffice(TimeStampedModel):
    """Faisalabad and Lahore today. Which regions each controls is data, not code."""

    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    name_ur = models.CharField(_("name (Urdu)"), max_length=120, blank=True)
    city = models.CharField(max_length=80)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@audited
class Region(TimeStampedModel):
    """A group of cities/branches supervised by one head office."""

    head_office = models.ForeignKey(HeadOffice, on_delete=models.PROTECT, related_name="regions")
    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    name_ur = models.CharField(_("name (Urdu)"), max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["head_office__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.head_office})"


@audited
class Branch(TimeStampedModel):
    class Ownership(models.TextChoices):
        COMPANY = "company", _("Company-owned")
        FRANCHISE = "franchise", _("Franchise")

    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=160)
    name_ur = models.CharField(_("name (Urdu)"), max_length=160, blank=True)
    head_office = models.ForeignKey(HeadOffice, on_delete=models.PROTECT, related_name="branches")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="branches", null=True, blank=True)
    ownership = models.CharField(max_length=20, choices=Ownership.choices, default=Ownership.FRANCHISE)
    royalty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("8.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text=_("Head office royalty on monthly fee collections. Company-owned branches use 0."),
    )
    city = models.CharField(max_length=80)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["head_office__name", "name"]
        verbose_name_plural = "branches"

    def __str__(self):
        return self.name

    def clean(self):
        if self.region_id and self.region.head_office_id != self.head_office_id:
            raise ValidationError({"region": _("Region belongs to a different head office.")})


@audited
class AcademicSession(TimeStampedModel):
    """A school year, e.g. 2026-27. One session is current across the network."""

    name = models.CharField(max_length=20, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_on__gt=models.F("starts_on")), name="session_ends_after_start"),
            models.UniqueConstraint(fields=["is_current"], condition=Q(is_current=True), name="one_current_session"),
        ]

    def __str__(self):
        return self.name
