from pathlib import Path

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.organisation.models import Campus

from .models import (
    LEVELS,
    MARKS,
    SUBJECTS,
    Application,
    Candidate,
    CandidateCV,
    Education,
    Experience,
    InterviewSheet,
    Post,
    Vacancy,
)

FILE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
FILE_MAX_BYTES = 8 * 1024 * 1024
DATE = forms.DateInput(attrs={"type": "date"})


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Photos of each page of a CV (or one PDF), chosen together."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, list | tuple) else ([data] if data else [])
        out = []
        for f in files:
            f = super().clean(f, initial)
            if Path(f.name).suffix.lower() not in FILE_TYPES:
                raise forms.ValidationError(_("Upload photos (JPG, PNG) or a PDF."))
            if f.size > FILE_MAX_BYTES:
                raise forms.ValidationError(_("Each file can be up to 8 MB."))
            out.append(f)
        return out


def _ticks(choices):
    return forms.MultipleChoiceField(choices=choices, required=False, widget=forms.CheckboxSelectMultiple)


class CandidateForm(forms.ModelForm):
    subjects = _ticks(SUBJECTS)
    levels = _ticks(LEVELS)

    class Meta:
        model = Candidate
        fields = [
            "post", "campus", "full_name", "father_name", "gender", "mobile", "cnic", "email", "address",
            "qualification", "experience_years", "subjects", "levels", "salary_asked", "relevance",
            "relevance_note", "notes",
        ]  # fmt: skip
        widgets = {"notes": forms.Textarea(attrs={"rows": 2}), "relevance": forms.RadioSelect}

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["post"].queryset = Post.objects.filter(is_active=True) | Post.objects.filter(
            pk=getattr(self.instance, "post_id", None)
        )
        self.fields["campus"].queryset = Campus.objects.filter(branch=branch, is_active=True)
        self.fields["campus"].empty_label = _("Any campus")
        self.fields["mobile"].widget.attrs.update({"inputmode": "tel", "autocomplete": "off"})
        self.fields["cnic"].widget.attrs.update({"inputmode": "numeric", "placeholder": "33100-0000000-0"})
        self.fields["address"].help_text = _("As written on the CV.")
        self.fields["relevance_note"].widget.attrs["placeholder"] = _("e.g. lives far away, another city")


class ReceivedForm(forms.ModelForm):
    """When and how this CV came, and its photos or PDF."""

    files = MultipleFileField(label=_("CV photos or PDF"), required=False)

    class Meta:
        model = CandidateCV
        fields = ["received_on", "channel", "note"]
        widgets = {"received_on": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["received_on"].initial = timezone.localdate()

    def clean_received_on(self):
        day = self.cleaned_data["received_on"]
        if day > timezone.localdate():
            raise forms.ValidationError(_("The date cannot be in the future."))
        return day


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ["degree", "institute", "year"]
        widgets = {"year": forms.NumberInput(attrs={"inputmode": "numeric", "style": "max-inline-size:6rem"})}


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = ["organisation", "post", "level", "years"]
        widgets = {"years": forms.NumberInput(attrs={"step": "0.5", "style": "max-inline-size:6rem"})}


def candidate_formsets(data=None, instance=None):
    make = forms.inlineformset_factory
    kinds = (("education", Education, EducationForm), ("experience", Experience, ExperienceForm))
    return {
        prefix: make(Candidate, model, form=form, extra=1, can_delete=True)(
            data if data is not None and f"{prefix}-TOTAL_FORMS" in data else None,
            instance=instance or Candidate(),
            prefix=prefix,
        )
        for prefix, model, form in kinds
    }


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = ["post", "subject", "level", "campus", "openings", "needed_by", "notes"]
        widgets = {"needed_by": DATE}

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["post"].queryset = Post.objects.filter(is_active=True)
        self.fields["campus"].queryset = Campus.objects.filter(branch=branch, is_active=True)
        self.fields["campus"].empty_label = _("Any campus")


class StepForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["interview_at", "demo_class", "salary_offered", "joining_on", "note"]
        widgets = {"interview_at": forms.DateTimeInput(attrs={"type": "datetime-local"}), "joining_on": DATE}


class InterviewSheetForm(forms.ModelForm):
    class Meta:
        model = InterviewSheet
        fields = [
            "held_on", "interviewers", "subject_knowledge", "teaching", "communication", "character",
            "experience", "impression", "remarks", "decision",
        ]  # fmt: skip
        widgets = {"held_on": DATE, "remarks": forms.Textarea(attrs={"rows": 3}), "decision": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["held_on"].initial = timezone.localdate()
        for name, _heading, out_of in MARKS:
            self.fields[name].label = f"{self.fields[name].label} (/{out_of})"
            self.fields[name].widget.attrs.update({"min": 0, "max": out_of, "style": "max-inline-size:6rem"})


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["name", "is_teaching"]
