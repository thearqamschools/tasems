"""Payroll (M10). Rules confirmed by the project lead: every staff member has a fixed monthly salary; a day of
absence or (unpaid) leave is cut from it. Per-day rate = monthly salary ÷ days in that month."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


class PayMethod(models.TextChoices):
    CASH = "cash", _("Cash")
    BANK = "bank", _("Bank transfer")
    ONLINE = "online", _("Online (JazzCash / Easypaisa)")


@audited
class EmployeePay(BranchOwnedModel):
    """A staff member's fixed monthly salary and where it is paid. Kept apart from the staff record, so only
    people with payroll rights see salaries."""

    method = models.CharField(_("salary paid by"), max_length=8, choices=PayMethod.choices, default=PayMethod.CASH)
    employee = models.OneToOneField("hr.Employee", on_delete=models.CASCADE, related_name="pay")
    monthly_salary = models.DecimalField(
        _("monthly salary (Rs)"), **MONEY, validators=[MinValueValidator(Decimal("0"))]
    )
    bank_name = models.CharField(_("bank"), max_length=80, blank=True, help_text=_("Empty: paid in cash"))
    account_title = models.CharField(_("account title"), max_length=120, blank=True)
    account_number = models.CharField(_("account number / IBAN"), max_length=40, blank=True)

    class Meta:
        permissions = [("finalise_payroll", "Can finalise a month's payroll")]

    def __str__(self):
        return f"{self.employee}: {self.monthly_salary}"


@audited
class PayrollRun(BranchOwnedModel):
    """A month's payroll for a branch, finalised (locked). Payslips keep the figures as they were."""

    class Status(models.TextChoices):
        FINAL = "final", _("Finalised")
        CANCELLED = "cancelled", _("Cancelled")

    month = models.DateField(help_text=_("First day of the month"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.FINAL)
    finalised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "month"], condition=models.Q(status="final"), name="one_final_payroll_per_month"
            )
        ]

    def __str__(self):
        return f"Payroll {self.month:%b %Y} ({self.get_status_display()})"


class Payslip(BranchOwnedModel):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="payslips")
    designation = models.CharField(max_length=60, blank=True)
    monthly_salary = models.DecimalField(**MONEY)
    days_in_month = models.PositiveSmallIntegerField()
    days_employed = models.PositiveSmallIntegerField(help_text=_("Days of the month the person was on the staff"))
    absent_days = models.PositiveSmallIntegerField(default=0)
    leave_days = models.PositiveSmallIntegerField(default=0, help_text=_("Days of unpaid leave"))
    half_days = models.PositiveSmallIntegerField(default=0, help_text=_("Half days: half a day's pay is cut"))
    working_days = models.PositiveSmallIntegerField(default=0)
    is_manual = models.BooleanField(default=False)
    method = models.CharField(max_length=8, choices=PayMethod.choices, default=PayMethod.CASH)
    deduction = models.DecimalField(**MONEY)
    net_pay = models.DecimalField(**MONEY)
    bank_name = models.CharField(max_length=80, blank=True)
    account_title = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["employee__staff_type", "employee__full_name"]
        constraints = [models.UniqueConstraint(fields=["run", "employee"], name="one_payslip_per_run")]

    def __str__(self):
        return f"{self.employee} {self.run.month:%b %Y}: {self.net_pay}"

    @property
    def unpaid_days(self):
        return self.absent_days + self.leave_days


@audited
class SalaryChange(BranchOwnedModel):
    """An increment (or other change) of a staff member's monthly salary from a month on (project lead, 31 Oct
    2026). The salary of any month is the latest change from that month or earlier, so past months keep theirs."""

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="salary_changes")
    from_month = models.DateField(_("from month"))
    old_salary = models.DecimalField(_("salary before (Rs)"), **MONEY)
    new_salary = models.DecimalField(_("new salary (Rs)"), **MONEY, validators=[MinValueValidator(Decimal("0"))])
    reason = models.CharField(_("reason"), max_length=200, blank=True)
    approved_by = models.CharField(_("approved by"), max_length=120, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["employee", "from_month", "id"]

    @property
    def increase(self):
        return self.new_salary - self.old_salary


@audited
class ManualDays(BranchOwnedModel):
    """A month's attendance figures typed in for one person when the machine sheet cannot be used (machine out of
    order, wrong sheet). They replace the machine figures for that person and month (project lead, 31 Oct 2026)."""

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="manual_days")
    month = models.DateField()
    days_in_month = models.PositiveSmallIntegerField()
    working_days = models.PositiveSmallIntegerField(default=0)
    days_employed = models.PositiveSmallIntegerField()
    absent_days = models.PositiveSmallIntegerField(default=0)
    leave_days = models.PositiveSmallIntegerField(default=0)
    half_days = models.PositiveSmallIntegerField(default=0)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "month"], name="one_manual_days_per_month")]


@audited
class SalaryPayment(BranchOwnedModel):
    """The salary of one finalised month handed over to one person: when and how. Locked once recorded."""

    payslip = models.OneToOneField(Payslip, on_delete=models.PROTECT, related_name="payment")
    amount = models.DecimalField(**MONEY)
    paid_on = models.DateField(_("paid on"))
    method = models.CharField(_("paid by"), max_length=8, choices=PayMethod.choices)
    reference = models.CharField(_("reference"), max_length=60, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-paid_on"]
