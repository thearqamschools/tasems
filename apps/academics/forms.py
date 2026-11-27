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


class BellSetForm(forms.ModelForm):
    """A set of bell times for some classes in a campus (R18-3)."""

    class Meta:
        from .models import BellSet

        model = BellSet
        fields = ["name", "from_level", "to_level", "campus"]
        labels = {"name": _("Name"), "from_level": _("From class"), "to_level": _("To class"), "campus": _("Campus")}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.organisation.models import Campus

        from .models import ClassLevel

        levels = ClassLevel.objects.filter(is_active=True).order_by("sort_order")
        self.fields["from_level"].queryset = levels
        self.fields["to_level"].queryset = levels
        self.fields["from_level"].empty_label = _("— first class —")
        self.fields["to_level"].empty_label = _("— last class —")
        self.fields["campus"].queryset = Campus.objects.filter(branch=branch, is_active=True)
        self.fields["campus"].empty_label = _("Every campus")
        self.fields["name"].widget.attrs["placeholder"] = _("e.g. Play Group to Two")

    def clean(self):
        data = super().clean()
        low, high = data.get("from_level"), data.get("to_level")
        if low and high and low.sort_order > high.sort_order:
            self.add_error("to_level", _("The last class comes before the first class."))
        return data
