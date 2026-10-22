from pathlib import Path

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.fees.forms import PROOF_MAX_BYTES, PROOF_TYPES
from apps.fees.models import BankAccount

from .models import Expense, ExpenseHead, Income, IncomeHead

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["date", "head", "amount", "description", "paid_to", "paid_from", "bank", "reference", "attachment"]
        labels = {
            "date": _("Date"),
            "head": _("Expense head"),
            "amount": _("Amount (Rs)"),
            "description": _("What for"),
            "paid_to": _("Paid to"),
            "paid_from": _("Paid from"),
            "bank": _("Which bank"),
            "reference": _("Bill / cheque / transaction no."),
            "attachment": _("Bill photo (optional)"),
        }
        widgets = {"date": DATE, "paid_from": forms.RadioSelect, "reference": forms.TextInput(attrs={"dir": "ltr"})}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["head"].queryset = ExpenseHead.objects.filter(is_active=True)
        self.fields["bank"].queryset = BankAccount.objects.filter(branch=branch, is_active=True)
        self.fields["attachment"].widget.attrs["accept"] = ".jpg,.jpeg,.png,.pdf"

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("The date is in the future."))
        return value

    def clean_attachment(self):
        file = self.cleaned_data.get("attachment")
        if file and getattr(file, "size", None) is not None and file != self.instance.attachment:
            if Path(file.name).suffix.lower() not in PROOF_TYPES:
                raise forms.ValidationError(_("Attach a JPG, PNG or PDF file."))
            if file.size > PROOF_MAX_BYTES:
                raise forms.ValidationError(_("The file is larger than 5 MB."))
        return file

    def clean(self):
        data = super().clean()
        if data.get("paid_from") == Expense.PaidFrom.BANK and not data.get("bank"):
            self.add_error("bank", _("Choose the bank the money was paid from."))
        if data.get("paid_from") == Expense.PaidFrom.CASH:
            data["bank"] = None
            self.instance.bank = None
        return data


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ["date", "head", "amount", "description", "received_from", "received_in", "bank", "reference"]
        labels = {
            "date": _("Date"),
            "head": _("Income head"),
            "amount": _("Amount (Rs)"),
            "description": _("What for"),
            "received_from": _("Received from"),
            "received_in": _("Received in"),
            "bank": _("Which bank"),
            "reference": _("Receipt / cheque / transaction no."),
        }
        widgets = {"date": DATE, "received_in": forms.RadioSelect, "reference": forms.TextInput(attrs={"dir": "ltr"})}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["head"].queryset = IncomeHead.objects.filter(is_active=True)
        self.fields["bank"].queryset = BankAccount.objects.filter(branch=branch, is_active=True)

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("The date is in the future."))
        return value

    def clean(self):
        data = super().clean()
        if data.get("received_in") == "bank" and not data.get("bank"):
            self.add_error("bank", _("Choose the bank the money came in."))
        if data.get("received_in") == "cash":
            data["bank"] = None
            self.instance.bank = None
        return data


class OpeningBalanceForm(forms.Form):
    account = forms.ChoiceField(label=_("Account"))
    as_of = forms.DateField(label=_("Balance at the start of"), widget=DATE)
    amount = forms.DecimalField(label=_("Amount (Rs)"), max_digits=14, decimal_places=2)

    def __init__(self, *args, accounts, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].choices = [(key, label) for key, label, _bank in accounts if key != "online"]
