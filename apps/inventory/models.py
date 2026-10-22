"""Inventory (M11): books, uniforms and stationery each branch keeps and sells.

Stock is a ledger: every receipt, sale, issue, return and correction is one StockMove that is never edited; the
stock in hand is the sum of the moves. A cancelled sale adds moves that put the items back."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


@audited
class Item(BranchOwnedModel):
    class Category(models.TextChoices):
        BOOKS = "books", _("Books")
        STATIONERY = "stationery", _("Stationery")
        UNIFORM = "uniform", _("Uniform")
        OTHER = "other", _("Other")

    name = models.CharField(_("name"), max_length=120)
    category = models.CharField(_("category"), max_length=12, choices=Category.choices, default=Category.BOOKS)
    class_level = models.ForeignKey(
        "academics.ClassLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("class"),
    )
    barcode = models.CharField(
        _("barcode"), max_length=40, blank=True, help_text=_("Printed on the item, or your own code")
    )
    sale_price = models.DecimalField(_("sale price (Rs)"), **MONEY, validators=[MinValueValidator(Decimal("0"))])
    reorder_level = models.PositiveIntegerField(
        _("reorder level"), default=0, help_text=_("Warn when stock falls to this")
    )
    is_active = models.BooleanField(_("in use"), default=True)

    class Meta:
        ordering = ["category", "class_level__sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "barcode"], condition=~models.Q(barcode=""), name="unique_item_barcode_per_branch"
            )
        ]

    def __str__(self):
        return f"{self.name}{f' ({self.class_level})' if self.class_level_id else ''}"


class StockMove(BranchOwnedModel):
    class Kind(models.TextChoices):
        RECEIVED = "received", _("Received")
        SALE = "sale", _("Sold")
        ISSUE = "issue", _("Issued free")
        RETURN = "return", _("Returned")
        CORRECTION = "correction", _("Stock count correction")

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="moves")
    date = models.DateField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    quantity = models.IntegerField(help_text=_("Positive in, negative out"))
    unit_cost = models.DecimalField(**MONEY, null=True, blank=True, help_text=_("Purchase price, for stock received"))
    sale = models.ForeignKey("Sale", on_delete=models.PROTECT, null=True, blank=True, related_name="moves")
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date", "-pk"]
        indexes = [models.Index(fields=["branch", "item"]), models.Index(fields=["branch", "date"])]

    def __str__(self):
        return f"{self.date:%d %b %Y} {self.item}: {self.quantity:+d}"


@audited
class Sale(BranchOwnedModel):
    class PaidBy(models.TextChoices):
        CASH = "cash", _("Cash")
        BANK = "bank", _("Bank")
        FEES = "fees", _("Add to the student's fee account")

    number = models.PositiveIntegerField()
    date = models.DateField()
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    customer = models.CharField(max_length=120, blank=True)
    paid_by = models.CharField(max_length=6, choices=PaidBy.choices, default=PaidBy.CASH)
    bank = models.ForeignKey("fees.BankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    total = models.DecimalField(**MONEY)
    income = models.OneToOneField(
        "accounting.Income", on_delete=models.PROTECT, null=True, blank=True, related_name="sale"
    )
    charge = models.OneToOneField("fees.Charge", on_delete=models.PROTECT, null=True, blank=True, related_name="sale")
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "-number"]
        constraints = [models.UniqueConstraint(fields=["branch", "number"], name="unique_sale_number_per_branch")]

    def __str__(self):
        return f"Sale {self.number} — Rs {self.total}"


class SaleLine(BranchOwnedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(**MONEY)
    amount = models.DecimalField(**MONEY)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.item} × {self.quantity}"
