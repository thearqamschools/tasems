from decimal import Decimal
from pathlib import Path

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Section

from .models import BankAccount, Concession, FeeHead, Method, month_start

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
PROOF_TYPES = {".jpg", ".jpeg", ".png", ".pdf"}
PROOF_MAX_BYTES = 5 * 1024 * 1024


class MonthField(forms.DateField):
    """<input type="month"> → first day of that month."""

    widget = forms.DateInput(attrs={"type": "month"}, format="%Y-%m")
    input_formats = ["%Y-%m", "%Y-%m-%d"]

    def to_python(self, value):
        value = super().to_python(value)
        return month_start(value) if value else value


class GenerateForm(forms.Form):
    first_month = MonthField(label=_("From month"))
    last_month = MonthField(
        label=_("To month"), help_text=_("Same as 'From' for one month. E.g. June to July in July.")
    )
    due_on = forms.DateField(label=_("Due date"), widget=DATE)
    sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.none(),
        required=False,
        label=_("Only these classes"),
        help_text=_("Leave empty for the whole branch."),
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )

    def __init__(self, *args, branch, session, **kwargs):
        super().__init__(*args, **kwargs)
        if session:
            self.fields["sections"].queryset = (
                Section.objects.filter(branch=branch, session=session, is_active=True)
                .select_related("class_level")
                .order_by("class_level__sort_order", "name")
            )

    def clean(self):
        data = super().clean()
        first, last = data.get("first_month"), data.get("last_month")
        if first and last:
            if last < first:
                self.add_error("last_month", _("'To month' is before 'From month'."))
            elif (last.year - first.year) * 12 + last.month - first.month >= 12:
                self.add_error("last_month", _("At most 12 months on one voucher."))
        return data


class IssueForm(GenerateForm):
    """One student's voucher: months, plus admission/registration/annual or another charge."""

    other_head = forms.ModelChoiceField(
        queryset=FeeHead.objects.filter(kind=FeeHead.Kind.OTHER, is_active=True),
        required=False,
        label=_("Other charge"),
    )
    other_amount = forms.DecimalField(required=False, min_value=1, max_digits=12, decimal_places=2, label=_("Amount"))
    other_note = forms.CharField(required=False, max_length=200, label=_("What it is for"))

    def __init__(self, *args, one_time, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("sections")
        self.one_time = one_time  # [(head, suggested amount)]
        for head, amount in one_time:
            self.fields[f"h_{head.code}"] = forms.BooleanField(required=False, label=head.name)
            self.fields[f"a_{head.code}"] = forms.DecimalField(
                required=False, min_value=0, max_digits=12, decimal_places=2, initial=amount, label=_("Amount")
            )

    def clean(self):
        data = super().clean()
        if data.get("other_head") and not data.get("other_amount"):
            self.add_error("other_amount", _("Enter the amount."))
        for head, _amount in self.one_time:
            if data.get(f"h_{head.code}") and data.get(f"a_{head.code}") in (None, ""):
                self.add_error(f"a_{head.code}", _("Enter the amount."))
        return data


class PaymentForm(forms.Form):
    """Cash or Bank (one of the branch's banks); who received it is the signed-in person."""

    CASH, BANK = "cash", "bank"

    amount = forms.DecimalField(min_value=Decimal("1"), max_digits=12, decimal_places=2, label=_("Amount received"))
    paid_on = forms.DateField(label=_("Date paid"), widget=DATE)
    how = forms.ChoiceField(
        choices=[(CASH, _("Cash")), (BANK, _("Bank"))], widget=forms.RadioSelect, label=_("Received in")
    )
    bank = forms.ModelChoiceField(queryset=BankAccount.objects.none(), required=False, label=_("Which bank"))
    reference = forms.CharField(
        required=False,
        max_length=60,
        label=_("Transaction ID / slip number"),
        widget=forms.TextInput(attrs={"dir": "ltr"}),
    )
    attachment = forms.FileField(
        required=False,
        label=_("Attachment"),
        help_text=_("Optional: photo or screenshot of the receipt (JPG, PNG or PDF, up to 5 MB)."),
        widget=forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )
    note = forms.CharField(required=False, max_length=200, label=_("Note"))

    def __init__(self, *args, branch, full_amount=None, allow_partial=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_amount, self.allow_partial = full_amount, allow_partial
        self.fields["bank"].queryset = BankAccount.objects.filter(branch=branch, is_active=True)
        self.fields["bank"].widget.attrs["data-show-when-bank"] = ""
        if not self.fields["bank"].queryset.exists():
            self.fields["bank"].help_text = _("No banks yet: add them in Setup → Fee rates and vouchers.")

    def clean_paid_on(self):
        value = self.cleaned_data["paid_on"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("The date is in the future."))
        return value

    def clean_attachment(self):
        file = self.cleaned_data.get("attachment")
        if file:
            if Path(file.name).suffix.lower() not in PROOF_TYPES:
                raise forms.ValidationError(_("Attach a JPG, PNG or PDF file."))
            if file.size > PROOF_MAX_BYTES:
                raise forms.ValidationError(_("The file is larger than 5 MB."))
        return file

    def clean(self):
        data = super().clean()
        if data.get("how") == self.BANK and not data.get("bank"):
            self.add_error("bank", _("Choose the bank the money came in."))
        if data.get("how") == self.CASH:
            data["bank"] = None
        data["method"] = Method.BANK if data.get("how") == self.BANK else Method.COUNTER
        if not self.allow_partial and self.full_amount and data.get("amount") and data["amount"] < self.full_amount:
            self.add_error("amount", _("This branch accepts only the full amount."))
        return data


class QuickReceiveForm(PaymentForm):
    """Finance → Barcode: type or scan the Voucher ID and record the full amount due."""

    voucher_number = forms.CharField(
        max_length=20,
        label=_("Voucher ID"),
        widget=forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric", "autofocus": True, "autocomplete": "off"}),
    )
    field_order = ["voucher_number", "paid_on", "how", "bank", "reference", "attachment", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["amount"]


class ConcessionForm(forms.ModelForm):
    starts_on = MonthField(label=_("From month"))
    ends_on = MonthField(label=_("Until month"), required=False, help_text=_("Leave empty until stopped."))

    class Meta:
        model = Concession
        fields = ["head", "kind", "value", "starts_on", "ends_on", "reason"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head"].queryset = FeeHead.objects.filter(is_active=True).exclude(kind=FeeHead.Kind.FINE)
        self.fields["head"].initial = FeeHead.objects.filter(code="tuition").first()


class ReasonForm(forms.Form):
    reason = forms.CharField(max_length=200, label=_("Reason"))
