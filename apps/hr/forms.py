from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.phone import format_cnic, normalize_cnic, normalize_mobile
from apps.organisation.models import Campus

from .models import Employee, LeaveType, StaffDay

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "code",
            "full_name",
            "full_name_ur",
            "father_name",
            "gender",
            "cnic",
            "date_of_birth",
            "phone",
            "alt_phone",
            "email",
            "address",
            "designation",
            "staff_type",
            "campus",
            "qualification",
            "joined_on",
            "machine_id",
            "status",
            "left_on",
            "notes",
        ]
        widgets = {
            "date_of_birth": DATE,
            "joined_on": DATE,
            "left_on": DATE,
            "code": forms.TextInput(attrs={"dir": "ltr"}),
            "machine_id": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}),
            "cnic": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric", "placeholder": "33100-1234567-1"}),
            "phone": forms.TextInput(attrs={"dir": "ltr", "inputmode": "tel", "placeholder": "0300-1234567"}),
            "full_name_ur": forms.TextInput(attrs={"dir": "rtl", "lang": "ur", "class": "ur"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, branch, **kwargs):
        self.branch = branch
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["campus"].queryset = Campus.objects.filter(branch=branch, is_active=True)
        self.initial["cnic"] = format_cnic(self.instance.cnic)
        # Typed with dashes or spaces; stored as digits only after cleaning.
        for name, length in (("cnic", 17), ("phone", 16)):
            self.fields[name].max_length = length
            self.fields[name].validators = []
            self.fields[name].widget.attrs["maxlength"] = length
        if not self.instance.pk:
            self.fields.pop("status")
            self.fields.pop("left_on")

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        clash = Employee.objects.filter(branch=self.branch, code__iexact=code).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(_("This employee code is already used in this branch."))
        return code

    def clean_machine_id(self):
        value = self.cleaned_data.get("machine_id", "").strip()
        if (
            value
            and Employee.objects.filter(branch=self.branch, machine_id=value).exclude(pk=self.instance.pk).exists()
        ):
            raise forms.ValidationError(_("Another person already has this machine ID in this branch."))
        return value

    def clean_cnic(self):
        raw = self.cleaned_data.get("cnic", "").strip()
        if not raw:
            return ""
        cnic = normalize_cnic(raw)
        if cnic is None:
            raise forms.ValidationError(_("A CNIC has 13 digits, e.g. 33100-1234567-1."))
        return cnic

    def clean_phone(self):
        raw = self.cleaned_data.get("phone", "").strip()
        if not raw:
            return ""
        phone = normalize_mobile(raw)
        if phone is None:
            raise forms.ValidationError(_("Enter a Pakistani mobile number, e.g. 0300-1234567."))
        return phone


class LeaveForm(forms.Form):
    leave_type = forms.ModelChoiceField(queryset=LeaveType.objects.filter(is_active=True), label=_("Type of leave"))
    starts_on = forms.DateField(label=_("From"), widget=DATE)
    ends_on = forms.DateField(label=_("To"), widget=DATE)
    reason = forms.CharField(max_length=250, label=_("Reason"))

    def clean(self):
        data = super().clean()
        start, end = data.get("starts_on"), data.get("ends_on")
        if start and end:
            if end < start:
                self.add_error("ends_on", _("The last day is before the first day."))
            elif (end - start).days > 180:
                self.add_error("ends_on", _("Leave longer than 180 days must be split."))
            elif start < timezone.localdate().replace(day=1).replace(year=timezone.localdate().year - 1):
                self.add_error("starts_on", _("This date is too far in the past."))
        return data


CORRECTABLE = [
    (s, label)
    for s, label in StaffDay.Status.choices
    if s in ("present", "late", "half_day", "absent", "leave", "holiday", "off")
]


class CorrectionForm(forms.Form):
    status = forms.ChoiceField(choices=CORRECTABLE, label=_("Mark as"))
    first_in = forms.TimeField(required=False, label=_("Time in"), widget=TIME)
    last_out = forms.TimeField(required=False, label=_("Time out"), widget=TIME)
    note = forms.CharField(max_length=200, label=_("Reason"), help_text=_("e.g. machine was not working"))
