from decimal import Decimal
from pathlib import Path

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Section

from .models import BankAccount, Concession, FeeHead, Method, RoyaltyPayment, month_start

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
    """Generate vouchers: month → class (Hifz Boys / Girls apart) → section → which other fees to add."""

    HIFZ_BOYS, HIFZ_GIRLS = "hifz-boys", "hifz-girls"

    first_month = MonthField(label=_("Month"))
    last_month = MonthField(
        label=_("Until month (optional)"),
        required=False,
        help_text=_("Only to make one voucher for several months, e.g. June and July together."),
    )
    due_on = forms.DateField(label=_("Due date"), widget=DATE)
    level = forms.ChoiceField(label=_("Class"), required=False)
    section_name = forms.ChoiceField(label=_("Section"), required=False)
    heads = forms.ModelMultipleChoiceField(
        queryset=FeeHead.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Add these fees as well"),
        help_text=_("The monthly fee is always on the voucher. Earlier unpaid months and their fines come too."),
    )

    def __init__(self, *args, branch, session, **kwargs):
        super().__init__(*args, **kwargs)
        self.branch, self.session = branch, session
        sections = Section.objects.filter(branch=branch, session=session, is_active=True).select_related("class_level")
        self.sections = list(sections)
        levels = []
        for sec in sorted(self.sections, key=lambda s: s.class_level.sort_order):
            if sec.class_level.code != "hifz" and (str(sec.class_level_id), sec.class_level.name) not in levels:
                levels.append((str(sec.class_level_id), sec.class_level.name))
        if any(s.class_level.code == "hifz" and s.gender_group != "girls" for s in self.sections):
            levels.append((self.HIFZ_BOYS, _("Hifz Boys")))
        if any(s.class_level.code == "hifz" and s.gender_group != "boys" for s in self.sections):
            levels.append((self.HIFZ_GIRLS, _("Hifz Girls")))
        self.fields["level"].choices = [("", _("All classes")), *levels]
        names = sorted({s.name for s in self.sections})
        self.fields["section_name"].choices = [("", _("All sections")), *[(n, n) for n in names]]
        self.fields["heads"].queryset = FeeHead.objects.filter(is_active=True).exclude(
            kind__in=[FeeHead.Kind.MONTHLY, FeeHead.Kind.FINE, FeeHead.Kind.ONE_TIME]
        )

    def clean(self):
        data = super().clean()
        if data.get("first_month") and not data.get("last_month"):
            data["last_month"] = data["first_month"]
        if data.get("first_month") and data.get("last_month") and data["last_month"] < data["first_month"]:
            self.add_error("last_month", _("The last month is before the first month."))
        if "level" not in self.fields:
            return data
        level, name = data.get("level"), data.get("section_name")
        chosen = self.sections
        if level == self.HIFZ_BOYS:
            chosen = [s for s in chosen if s.class_level.code == "hifz" and s.gender_group != "girls"]
        elif level == self.HIFZ_GIRLS:
            chosen = [s for s in chosen if s.class_level.code == "hifz" and s.gender_group != "boys"]
        elif level:
            chosen = [s for s in chosen if str(s.class_level_id) == level]
        if name:
            chosen = [s for s in chosen if s.name == name]
        if (level or name) and not chosen:
            self.add_error("section_name", _("No section matches this class and section."))
        data["section_ids"] = [s.id for s in chosen] if (level or name) else None
        # Hifz classes are often mixed: Hifz Boys / Girls also means only the boys or only the girls.
        data["gender"] = {self.HIFZ_BOYS: "male", self.HIFZ_GIRLS: "female"}.get(level)
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
        for name in ("level", "section_name", "heads"):  # one student: class and fees are chosen below
            self.fields.pop(name)
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


class VoucherEditForm(forms.Form):
    """While receiving: change the other fees on this voucher or add one. The monthly fee stays as it is."""

    add_head = forms.ModelChoiceField(queryset=FeeHead.objects.none(), required=False, label=_("Add a fee"))
    add_amount = forms.DecimalField(required=False, min_value=1, max_digits=12, decimal_places=2, label=_("Amount"))
    note = forms.CharField(required=False, max_length=200, label=_("Note"))

    def __init__(self, *args, charges, heads, **kwargs):
        super().__init__(*args, **kwargs)
        self.charges = charges  # this voucher's charges that may be changed
        self.fields["add_head"].queryset = heads
        for c in charges:
            self.fields[f"c_{c.id}"] = forms.DecimalField(
                min_value=0,
                max_digits=12,
                decimal_places=2,
                initial=c.amount,
                label=f"{c.head.name} ({c.month:%b %Y})",
            )

    def charge_fields(self):
        return [self[f"c_{c.id}"] for c in self.charges]

    def clean(self):
        data = super().clean()
        if data.get("add_head") and not data.get("add_amount"):
            self.add_error("add_amount", _("Enter the amount."))
        data["amounts"] = {c.id: data[f"c_{c.id}"] for c in self.charges if data.get(f"c_{c.id}") is not None}
        data["additions"] = [(data["add_head"], data["add_amount"])] if data.get("add_head") else []
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


class RoyaltyPaymentForm(forms.ModelForm):
    month = MonthField(label=_("For the month of"))

    class Meta:
        model = RoyaltyPayment
        fields = ["month", "amount", "paid_on", "reference", "attachment", "note"]
        labels = {
            "amount": _("Amount (Rs)"),
            "paid_on": _("Date received"),
            "reference": _("Deposit slip / transaction ID"),
            "attachment": _("Attachment (photo of the slip)"),
            "note": _("Note"),
        }
        widgets = {"paid_on": DATE, "reference": forms.TextInput(attrs={"dir": "ltr"})}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["attachment"].widget.attrs["accept"] = ".jpg,.jpeg,.png,.pdf"

    def clean_paid_on(self):
        value = self.cleaned_data["paid_on"]
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
