from django import forms
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Section
from apps.core.phone import normalize_mobile

from .models import Student, StudentGuardian

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class StudentForm(forms.ModelForm):
    """One screen for a student, their class this session and their primary contact."""

    section = forms.ModelChoiceField(
        queryset=Section.objects.none(), required=False, label=_("Class and section (this session)")
    )
    roll_no = forms.IntegerField(required=False, min_value=1, label=_("Roll number"))
    guardian_name = forms.CharField(max_length=150, label=_("Parent / guardian name"))
    guardian_name_ur = forms.CharField(max_length=150, required=False, label=_("Parent / guardian name (Urdu)"))
    guardian_phone = forms.CharField(
        max_length=20,
        label=_("Parent mobile / WhatsApp"),
        help_text=_("e.g. 0300-1234567"),
        widget=forms.TextInput(attrs={"inputmode": "tel", "dir": "ltr"}),
    )
    relationship = forms.ChoiceField(choices=StudentGuardian.Relationship.choices, label=_("Relationship"))

    class Meta:
        model = Student
        fields = [
            "admission_no",
            "first_name",
            "last_name",
            "full_name_ur",
            "gender",
            "date_of_birth",
            "admission_date",
            "b_form_no",
            "is_hifz",
            "status",
        ]
        widgets = {
            "date_of_birth": DATE,
            "admission_date": DATE,
            "admission_no": forms.TextInput(attrs={"dir": "ltr"}),
            "b_form_no": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}),
            "full_name_ur": forms.TextInput(attrs={"dir": "rtl", "lang": "ur", "class": "ur"}),
        }

    def __init__(self, *args, branch, session, **kwargs):
        self.branch = branch
        self.session = session
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["guardian_name_ur"].widget.attrs.update({"dir": "rtl", "lang": "ur", "class": "ur"})
        if session:
            self.fields["section"].queryset = (
                Section.objects.filter(branch=branch, session=session, is_active=True)
                .select_related("class_level")
                .order_by("class_level__sort_order", "name")
            )
        else:
            self.fields["section"].help_text = _("No current session is set, so the class can be added later.")
        if not self.instance.pk:
            self.fields.pop("status")

    def clean_admission_no(self):
        value = self.cleaned_data["admission_no"].strip()
        clash = Student.objects.filter(branch=self.branch, admission_no__iexact=value).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(_("This admission number is already used in this branch."))
        return value

    def clean_guardian_phone(self):
        phone = normalize_mobile(self.cleaned_data["guardian_phone"])
        if phone is None:
            raise forms.ValidationError(_("Enter a Pakistani mobile number, e.g. 0300-1234567."))
        return phone

    def clean(self):
        data = super().clean()
        section, gender = data.get("section"), data.get("gender")
        if section and gender and section.gender_group != "mixed":
            if {"boys": "male", "girls": "female"}[section.gender_group] != gender:
                self.add_error(
                    "section", _("This section is for %(g)s only.") % {"g": section.get_gender_group_display()}
                )
        return data
