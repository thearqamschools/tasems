"""Fees: what a student owes, the vouchers parents pay with, and what was received.

How the money is kept (DECISIONS D-033):

* Every amount owed is a **Charge** (one fee head for one month, e.g. Tuition Oct 2026).
* Every amount received is a **Payment** (counter, Askari Bank, bank transfer, JazzCash, Alfa app …).
* A student's balance is simply charges minus payments. Nothing is ever overwritten:
  a wrong charge is cancelled and a wrong payment is reversed, both with a reason.
* A **Voucher** is the printed bill. It lists the new charges, any unpaid balance
  from earlier months (arrears) and the late fine shown as "Payable after due date".
* Payments are matched to the oldest charges first (PaymentAllocation), which tells
  which months are paid and how much tuition was collected for royalty statements.

Fee amounts are per branch (each franchise sets its own) and per class.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel

MONEY = {"max_digits": 12, "decimal_places": 2}
POSITIVE = [MinValueValidator(Decimal("0"))]


def month_start(date):
    return dt.date(date.year, date.month, 1)


def add_months(date, n):
    index = date.year * 12 + date.month - 1 + n
    return dt.date(index // 12, index % 12 + 1, 1)


def months_between(first, last):
    """Every month from `first` to `last`, inclusive."""
    out, current = [], month_start(first)
    while current <= month_start(last):
        out.append(current)
        current = add_months(current, 1)
    return out


@audited
class FeeHead(TimeStampedModel):
    """A column on the voucher: Admission, Registration, Tuition, Annual, S.V.W., Fine … (network-wide)."""

    class Kind(models.TextChoices):
        MONTHLY = "monthly", _("Every month")
        YEARLY = "yearly", _("Once a year, in the months listed")
        SEASONAL = "seasonal", _("In the months listed, when an amount is set for that year")
        ONE_TIME = "one_time", _("Chosen on a voucher (e.g. at admission)")
        FINE = "fine", _("Late fine (automatic)")
        OTHER = "other", _("Added by hand")

    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=60)
    short_name = models.CharField(max_length=20, help_text=_("Voucher column heading, e.g. Reg., S.V.W."))
    name_ur = models.CharField(_("name (Urdu)"), max_length=60, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    charge_months = models.JSONField(
        default=list, blank=True, help_text=_("For yearly and seasonal heads: month numbers, e.g. [4] for April.")
    )
    counts_for_royalty = models.BooleanField(
        default=False, help_text=_("Collections of this head count towards the franchise royalty (monthly fee).")
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


@audited
class FeeRate(BranchOwnedModel):
    """How much a head costs in one branch, for one class or all classes, from a date onwards."""

    head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="rates")
    class_level = models.ForeignKey(
        "academics.ClassLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Leave empty for all classes. A class's own rate wins over the all-classes rate."),
    )
    amount = models.DecimalField(**MONEY, validators=POSITIVE)
    sibling_amount = models.DecimalField(
        **MONEY,
        null=True,
        blank=True,
        validators=POSITIVE,
        help_text=_("Amount for brothers and sisters (same father's CNIC) after the first child, e.g. 4000."),
    )
    effective_from = models.DateField(help_text=_("First month this amount applies to."))

    class Meta:
        ordering = ["head__sort_order", "class_level__sort_order", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "head", "class_level", "effective_from"],
                name="one_rate_per_branch_head_class_date",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return f"{self.head} {self.class_level or _('all classes')}: {self.amount}"


@audited
class BranchFeeSettings(TimeStampedModel):
    """Due date, late fine and the bank details printed on this branch's vouchers.
    Head office or the branch accountant can change these at any time (Setup → Branch fee settings)."""

    branch = models.OneToOneField("organisation.Branch", on_delete=models.CASCADE, related_name="fee_settings")
    due_day = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1), MaxValueValidator(28)], help_text=_("Last day to pay, e.g. 10")
    )
    late_fine = models.DecimalField(**MONEY, default=Decimal("200"), validators=POSITIVE)
    bank_name = models.CharField(max_length=80, blank=True)
    bank_branch = models.CharField(max_length=120, blank=True)
    account_title = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    receipt_whatsapp = models.CharField(
        max_length=20, blank=True, help_text=_("Parents send online payment receipts to this WhatsApp number.")
    )
    voucher_note = models.CharField(
        max_length=200, blank=True, help_text=_("One line under each voucher copy, e.g. how to pay online.")
    )
    back_title = models.CharField(max_length=80, default="Fee Payment Options")
    back_notes_ur = models.TextField(
        _("special instructions (Urdu)"), blank=True, help_text=_("One instruction per line, printed on the back.")
    )
    back_notes_en = models.TextField(_("special instructions (English)"), blank=True)
    back_footer_ur = models.CharField(_("closing line (Urdu)"), max_length=200, blank=True)
    print_back_side = models.BooleanField(default=True)
    allow_partial_payment = models.BooleanField(
        default=True, help_text=_("Counter staff may accept less than the full amount.")
    )

    class Meta:
        verbose_name_plural = "branch fee settings"

    def __str__(self):
        return f"Fee settings — {self.branch}"

    @classmethod
    def for_branch(cls, branch):
        return cls.objects.filter(branch=branch).first() or cls(branch=branch)

    def fill(self, text):
        """Replaces {bank_name}, {account_title}, {account_number}, {whatsapp} in instruction text."""
        return (
            (text or "")
            .replace("{bank_name}", self.bank_name)
            .replace("{account_title}", self.account_title)
            .replace("{account_number}", self.account_number)
            .replace("{whatsapp}", self.receipt_whatsapp)
        )


class Method(models.TextChoices):
    COUNTER = "counter", _("Cash at school")
    BANK_BRANCH = "bank_branch", _("Deposited at bank with voucher")
    BANK_TRANSFER = "bank_transfer", _("Bank transfer")
    JAZZCASH = "jazzcash", _("JazzCash")
    ALFA = "alfa", _("Bank Alfalah (Alfa app)")
    OTHER = "other", _("Other")


@audited
class PaymentChannel(TimeStampedModel):
    """One way of paying, printed on the back of the voucher. Text may use {bank_name},
    {account_title}, {account_number} and {whatsapp}; they are filled from the branch's fee settings."""

    branch = models.ForeignKey(
        "organisation.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Leave empty to show for every branch that has none of its own."),
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    title = models.CharField(max_length=80)
    steps_en = models.TextField(_("steps (English)"), help_text=_("One step per line."))
    steps_ur = models.TextField(_("steps (Urdu)"), blank=True, help_text=_("One step per line."))
    note_en = models.CharField(max_length=200, blank=True)
    note_ur = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.title

    @classmethod
    def for_branch(cls, branch):
        own = cls.objects.filter(branch=branch, is_active=True)
        return list(own) if own.exists() else list(cls.objects.filter(branch__isnull=True, is_active=True))


class VoucherCounter(models.Model):
    """Voucher numbers are unique across the whole network, so bank and app payments can be traced
    by Voucher ID alone. `next_number` can be set above the old system's last number."""

    next_number = models.PositiveBigIntegerField(default=1000001)

    def __str__(self):
        return f"Next voucher number {self.next_number}"


class Voucher(BranchOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Not paid")
        PAID = "paid", _("Paid")
        SUPERSEDED = "superseded", _("Carried to a newer voucher")
        CANCELLED = "cancelled", _("Cancelled")

    number = models.PositiveBigIntegerField(unique=True)
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="vouchers")
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    first_month = models.DateField()
    last_month = models.DateField()
    issued_on = models.DateField()
    due_on = models.DateField()
    arrears = models.DecimalField(**MONEY, default=0, help_text=_("Unpaid balance from earlier vouchers"))
    current = models.DecimalField(**MONEY, default=0, help_text=_("New charges on this voucher"))
    payable = models.DecimalField(**MONEY, default=0, help_text=_("To pay by the due date"))
    late_fine = models.DecimalField(**MONEY, default=0, help_text=_("Added if paid after the due date"))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-first_month", "number"]
        indexes = [
            models.Index(fields=["branch", "first_month"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self):
        return f"Voucher {self.number} — {self.student}"

    @property
    def payable_after_due(self):
        return self.payable + self.late_fine

    @property
    def months(self):
        return months_between(self.first_month, self.last_month)


class Charge(BranchOwnedModel):
    class Source(models.TextChoices):
        AUTO = "auto", _("Monthly billing")
        MANUAL = "manual", _("Added by staff")
        FINE = "fine", _("Late fine")

    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="fee_charges")
    head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="+")
    month = models.DateField(help_text=_("First day of the month the charge is for"))
    gross = models.DecimalField(**MONEY, validators=POSITIVE)
    discount = models.DecimalField(**MONEY, default=0, validators=POSITIVE)
    amount = models.DecimalField(**MONEY, validators=POSITIVE, help_text=_("gross − discount"))
    discount_reason = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.AUTO)
    voucher = models.ForeignKey(Voucher, on_delete=models.PROTECT, null=True, blank=True, related_name="charges")
    fine_for = models.OneToOneField(
        Voucher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fine_charge",
        help_text=_("Late voucher"),
    )
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_cancelled = models.BooleanField(default=False)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["month", "head__sort_order", "pk"]
        constraints = [
            # Monthly billing can never charge the same head twice for the same month.
            models.UniqueConstraint(
                fields=["student", "head", "month"],
                condition=Q(source="auto", is_cancelled=False),
                name="one_auto_charge_per_head_month",
            ),
            models.CheckConstraint(condition=Q(amount=models.F("gross") - models.F("discount")), name="net_amount"),
        ]
        indexes = [models.Index(fields=["branch", "month"]), models.Index(fields=["student", "is_cancelled"])]

    def __str__(self):
        return f"{self.head} {self.month:%b %Y}: {self.amount}"


@audited
class Payment(BranchOwnedModel):
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="fee_payments")
    voucher = models.ForeignKey(Voucher, on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("1"))])
    paid_on = models.DateField()
    method = models.CharField(max_length=20, choices=Method.choices)
    reference = models.CharField(
        max_length=60, blank=True, help_text=_("Bank or app transaction ID, deposit slip number")
    )
    note = models.CharField(max_length=200, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reverse_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-paid_on", "-pk"]
        permissions = [("view_royalty", "Can see royalty statements")]
        indexes = [models.Index(fields=["branch", "paid_on"]), models.Index(fields=["student", "is_reversed"])]

    def __str__(self):
        return f"Receipt {self.receipt_no}: {self.amount} ({self.get_method_display()})"

    @property
    def receipt_no(self):
        return f"R-{self.pk}"


class PaymentAllocation(BranchOwnedModel):
    """Which charge a payment paid off (oldest first). Rebuilt for the student after every change."""

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE, related_name="allocations")
    amount = models.DecimalField(**MONEY)

    class Meta:
        indexes = [models.Index(fields=["branch", "charge"])]


@audited
class Concession(BranchOwnedModel):
    """A special discount. It only applies after the principal or a director approves it."""

    class Kind(models.TextChoices):
        PERCENT = "percent", _("Percentage off")
        AMOUNT = "amount", _("Fixed amount off")

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for approval")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Not approved")
        ENDED = "ended", _("Ended")

    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="concessions")
    head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    value = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    starts_on = models.DateField(help_text=_("First month"))
    ends_on = models.DateField(null=True, blank=True, help_text=_("Last month; empty = until stopped"))
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("approve_concession", "Can approve or reject special discounts")]

    def __str__(self):
        value = f"{self.value}%" if self.kind == self.Kind.PERCENT else f"Rs {self.value}"
        return f"{self.student} — {self.head} {value}"

    def clean(self):
        if self.kind == self.Kind.PERCENT and self.value and self.value > 100:
            raise ValidationError({"value": _("A percentage cannot be more than 100.")})
        if self.ends_on and self.starts_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": _("The last month is before the first month.")})

    def covers(self, month):
        return month_start(self.starts_on) <= month and (self.ends_on is None or month <= month_start(self.ends_on))

    def discount_on(self, gross):
        if self.kind == self.Kind.PERCENT:
            off = (gross * self.value / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        else:
            off = self.value
        return min(off, gross)
