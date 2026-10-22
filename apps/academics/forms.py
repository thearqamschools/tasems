from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Period

TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class PeriodForm(forms.ModelForm):
    class Meta:
        model = Period
        fields = ["number", "label", "starts_at", "ends_at", "is_break"]
        labels = {
            "number": _("No."),
            "label": _("Name (optional)"),
            "starts_at": _("Starts"),
            "ends_at": _("Ends"),
            "is_break": _("Break"),
        }
        widgets = {"starts_at": TIME, "ends_at": TIME, "number": forms.NumberInput(attrs={"min": 1, "max": 20})}
        help_texts = {"number": "", "label": ""}

    def validate_unique(self):
        pass  # the branch is set when saving; the database still refuses two periods with one number


DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class HolidayForm(forms.Form):
    starts_on = forms.DateField(label=_("From"), widget=DATE)
    ends_on = forms.DateField(
        label=_("To (optional)"), widget=DATE, required=False, help_text=_("For several days, e.g. Eid holidays.")
    )
    name = forms.CharField(label=_("Holiday"), max_length=100, help_text=_("e.g. Eid ul Fitr, Quaid-e-Azam Day"))
    students_off = forms.BooleanField(label=_("Students off (no attendance or diary)"), required=False, initial=True)
    staff_off = forms.BooleanField(label=_("Staff off (not counted absent)"), required=False, initial=True)
    everywhere = forms.BooleanField(label=_("For every branch of the network"), required=False)

    def __init__(self, *args, network=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not network:
            del self.fields["everywhere"]

    def clean(self):
        data = super().clean()
        start = data.get("starts_on")
        if start:
            data["ends_on"] = data.get("ends_on") or start
            if data["ends_on"] < start:
                self.add_error("ends_on", _("The last day is before the first day."))
            elif (data["ends_on"] - start).days > 92:
                self.add_error("ends_on", _("At most three months at a time."))
        if not data.get("students_off") and not data.get("staff_off"):
            self.add_error("students_off", _("Choose students, staff or both."))
        return data
