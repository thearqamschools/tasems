"""Branch expenses — the first part of accounting (roadmap M9; requested by the project lead 19 Oct 2026).

Each expense says what it was for (head), how much, who it was paid to, where the money came from
(cash in hand or one of the branch's banks) and who recorded it. Cancelling keeps the record with a reason.
"""

import secrets
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel


@audited
class ExpenseHead(TimeStampedModel):
    """What money is spent on (the same list for every branch)."""

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


def bill_path(expense, filename):
    """Private folder and a random name; opened only through TASEMS."""
    return f"private/expense-bills/{expense.branch_id}/{secrets.token_hex(16)}{Path(filename).suffix.lower()}"


@audited
class Expense(BranchOwnedModel):
    class PaidFrom(models.TextChoices):
        CASH = "cash", _("Cash in hand")
        BANK = "bank", _("Bank")

    date = models.DateField()
    head = models.ForeignKey(ExpenseHead, on_delete=models.PROTECT, related_name="expenses")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("1"))])
    description = models.CharField(max_length=200)
    paid_to = models.CharField(max_length=120, blank=True, help_text=_("Shop, company or person paid"))
    paid_from = models.CharField(max_length=10, choices=PaidFrom.choices, default=PaidFrom.CASH)
    bank = models.ForeignKey(
        "fees.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="expenses"
    )
    reference = models.CharField(max_length=60, blank=True, help_text=_("Bill, cheque or transaction number"))
    attachment = models.FileField(upload_to=bill_path, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_cancelled = models.BooleanField(default=False)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "-pk"]
        indexes = [models.Index(fields=["branch", "date"])]

    def __str__(self):
        return f"{self.date:%d %b %Y} {self.head}: {self.amount}"

    @property
    def paid_from_label(self):
        return self.bank.name if self.paid_from == self.PaidFrom.BANK and self.bank_id else self.get_paid_from_display()
