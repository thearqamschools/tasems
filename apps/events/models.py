"""Events & Tickets (project lead, 30 Oct 2026): trips, Eid Milan, Summer Gala, farewell and other school events.

Tickets are sold at the office without a voucher and printed as a receipt on the branch's receipt printer. Each
event keeps its own account (tickets sold, refunds, expenses, profit or loss); it is not part of school fees or the
school's cash book. Receipts and expenses are never deleted: a refund or a cancelled expense keeps its record."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel

MONEY = {"max_digits": 12, "decimal_places": 2}
NOT_NEGATIVE = [MinValueValidator(Decimal("0"))]


@audited
class Event(BranchOwnedModel):
    class Kind(models.TextChoices):
        TRIP = "trip", _("Trip")
        EID_MILAN = "eid_milan", _("Eid Milan party")
        GALA = "gala", _("Summer Gala")
        FAREWELL = "farewell", _("Farewell")
        SPORTS = "sports", _("Sports day")
        FUNCTION = "function", _("Annual function")
        OTHER = "other", _("Other")

    name = models.CharField(_("name"), max_length=120)
    kind = models.CharField(_("type"), max_length=12, choices=Kind.choices, default=Kind.TRIP)
    date = models.DateField(_("date"))
    venue = models.CharField(_("place"), max_length=150, blank=True)
    guest_price = models.DecimalField(
        _("extra ticket (Rs)"),
        **MONEY,
        default=0,
        validators=NOT_NEGATIVE,
        help_text=_("For parents or guests who come with the student. 0: no extra tickets."),
    )
    notes = models.TextField(_("notes"), blank=True)
    is_open = models.BooleanField(_("tickets on sale"), default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.name} ({self.date:%d %b %Y})"


class EventClass(BranchOwnedModel):
    """A class that takes part, with its ticket price."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="classes")
    class_level = models.ForeignKey("academics.ClassLevel", on_delete=models.PROTECT, related_name="+")
    price = models.DecimalField(_("ticket (Rs)"), **MONEY, validators=NOT_NEGATIVE)

    class Meta:
        ordering = ["class_level__sort_order"]
        constraints = [models.UniqueConstraint(fields=["event", "class_level"], name="unique_event_class")]


class TicketSale(BranchOwnedModel):
    class PaidBy(models.TextChoices):
        CASH = "cash", _("Cash")
        BANK = "bank", _("Bank")
        ONLINE = "online", _("JazzCash / Easypaisa")

    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="sales")
    number = models.PositiveIntegerField(_("receipt no."))
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="ticket_sales")
    class_level = models.ForeignKey("academics.ClassLevel", on_delete=models.PROTECT, related_name="+")
    section_name = models.CharField(max_length=20, blank=True)
    student_tickets = models.PositiveSmallIntegerField(default=1)
    student_price = models.DecimalField(**MONEY)
    guest_tickets = models.PositiveSmallIntegerField(_("extra tickets"), default=0)
    guest_price = models.DecimalField(**MONEY, default=0)
    amount = models.DecimalField(_("amount (Rs)"), **MONEY)
    paid_by = models.CharField(_("paid by"), max_length=8, choices=PaidBy.choices, default=PaidBy.CASH)
    reference = models.CharField(_("reference"), max_length=60, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    received_at = models.DateTimeField(auto_now_add=True)
    is_refunded = models.BooleanField(default=False)
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["event", "number"], name="unique_ticket_receipt_no")]
        permissions = [("refund_ticketsale", "Can refund event tickets")]

    def __str__(self):
        return f"{self.event.name} · {self.receipt_no}"

    @property
    def receipt_no(self):
        return f"EV{self.event_id}-{self.number:04d}"

    @property
    def tickets(self):
        return self.student_tickets + self.guest_tickets


class EventExpense(BranchOwnedModel):
    class Head(models.TextChoices):
        TRANSPORT = "transport", _("Transport")
        FOOD = "food", _("Food and drinks")
        VENUE = "venue", _("Venue and entry tickets")
        DECORATION = "decoration", _("Decoration and sound")
        GIFTS = "gifts", _("Gifts and prizes")
        OTHER = "other", _("Other")

    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="expenses")
    head = models.CharField(_("for"), max_length=12, choices=Head.choices, default=Head.TRANSPORT)
    description = models.CharField(_("details"), max_length=200, blank=True)
    amount = models.DecimalField(_("amount (Rs)"), **MONEY, validators=[MinValueValidator(Decimal("1"))])
    paid_to = models.CharField(_("paid to"), max_length=120, blank=True)
    date = models.DateField(_("date"))
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
