from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import ClassLevel
from apps.accounts.models import User
from apps.core.phone import normalize_mobile

from .models import FollowUp, Inquiry

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = [
            "child_name",
            "gender",
            "date_of_birth",
            "class_level",
            "is_hifz",
            "parent_name",
            "phone",
            "alt_phone",
            "area",
            "current_school",
            "source",
            "referred_by",
            "assigned_to",
            "next_follow_up",
            "notes",
        ]
        widgets = {
            "date_of_birth": DATE,
            "next_follow_up": DATE,
            "phone": forms.TextInput(attrs={"inputmode": "tel", "dir": "ltr", "placeholder": "0300-1234567"}),
            "alt_phone": forms.TextInput(attrs={"inputmode": "tel", "dir": "ltr"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"notes": _("Description"), "source": _("Where did they hear about us?")}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["class_level"].queryset = ClassLevel.objects.filter(is_active=True).order_by("sort_order")
        staff = User.objects.filter(
            is_active=True,
            role_assignments__branch=branch,
            role_assignments__role__permissions__codename="change_inquiry",
        ).distinct()
        self.fields["assigned_to"].queryset = staff
        self.fields["assigned_to"].label = _("Follow-up by")
        self.fields["phone"].max_length = 16
        self.fields["phone"].validators = []
        self.fields["phone"].widget.attrs["maxlength"] = 16

    def clean_phone(self):
        phone = normalize_mobile(self.cleaned_data.get("phone"))
        if phone is None:
            raise forms.ValidationError(_("Enter a Pakistani mobile number, e.g. 0300-1234567."))
        return phone

    def clean_date_of_birth(self):
        value = self.cleaned_data.get("date_of_birth")
        if value and value > timezone.localdate():
            raise forms.ValidationError(_("Date of birth is in the future"))
        return value


class FollowUpForm(forms.Form):
    kind = forms.ChoiceField(
        choices=[c for c in FollowUp.Kind.choices if c[0] != FollowUp.Kind.STATUS], label=_("What happened")
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("Note"))
    status = forms.ChoiceField(
        choices=[("", _("— no change —"))] + list(Inquiry.Status.choices), required=False, label=_("Move to")
    )
    lost_reason = forms.ChoiceField(
        choices=[("", "—")] + list(Inquiry.LostReason.choices), required=False, label=_("Reason (if not joining)")
    )
    visit_at = forms.DateTimeField(
        required=False,
        label=_("Campus visit on"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    next_follow_up = forms.DateField(required=False, label=_("Next follow-up"), widget=DATE)

    def clean(self):
        data = super().clean()
        status = data.get("status")
        if status == Inquiry.Status.LOST and not data.get("lost_reason"):
            self.add_error("lost_reason", _("Choose why the family is not joining."))
        if status == Inquiry.Status.ADMITTED:
            self.add_error("status", _("Use “Make student record” to admit the child."))
        if status == Inquiry.Status.VISIT and not data.get("visit_at"):
            self.add_error("visit_at", _("Enter the date and time of the visit."))
        if status not in (Inquiry.Status.LOST,) and not data.get("next_follow_up"):
            self.add_error("next_follow_up", _("Choose when to follow up next."))
        if not data.get("note") and data.get("kind") != FollowUp.Kind.STATUS and not status:
            self.add_error("note", _("Write what was discussed."))
        return data
