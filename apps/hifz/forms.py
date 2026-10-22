from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import PARAS, HifzLesson, ParaTest

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class LessonRow(forms.ModelForm):
    """One student's line on the day's sheet (prefixed with the student id)."""

    class Meta:
        model = HifzLesson
        fields = [
            "status", "sabaq_para", "sabaq", "sabaq_lines", "sabaq_mistakes", "sabqi", "sabqi_mistakes", "manzil",
            "manzil_mistakes", "grade", "remarks",
        ]  # fmt: skip


class ParaTestForm(forms.ModelForm):
    class Meta:
        model = ParaTest
        fields = ["para", "tested_on", "result", "mistakes", "before_joining", "remarks"]
        labels = {"para": _("Para"), "tested_on": _("Date"), "result": _("Result"), "mistakes": _("Mistakes"),
                  "before_joining": _("Memorised before joining"), "remarks": _("Remarks")}  # fmt: skip
        widgets = {"tested_on": DATE, "result": forms.RadioSelect, "para": forms.Select(choices=[])}

    def __init__(self, *args, passed=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["para"].widget.choices = [(n, n) for n in range(1, PARAS + 1) if n not in passed]

    def clean_tested_on(self):
        value = self.cleaned_data["tested_on"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("The date is in the future."))
        return value
