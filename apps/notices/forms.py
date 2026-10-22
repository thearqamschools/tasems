from pathlib import Path

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import ClassLevel

from .models import MessageTemplate, Notice

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
FILE_TYPES = {".pdf", ".jpg", ".jpeg", ".png"}


class NoticeForm(forms.ModelForm):
    where = forms.ChoiceField(label=_("Where"))

    class Meta:
        model = Notice
        fields = ["title", "body", "audience", "class_levels", "publish_on", "expires_on", "attachment"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 7}),
            "publish_on": DATE,
            "expires_on": DATE,
            "class_levels": forms.CheckboxSelectMultiple,
        }
        help_texts = {"attachment": _("Optional: PDF or photo, up to 5 MB.")}

    def __init__(self, *args, where_choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["where"].choices = where_choices
        self.fields["class_levels"].queryset = ClassLevel.objects.filter(is_active=True)
        self.fields["publish_on"].initial = timezone.localdate()
        self.fields["attachment"].widget.attrs["accept"] = ".pdf,.jpg,.jpeg,.png"
        self.order_fields(["where", "audience", "title", "body", "class_levels", "publish_on", "expires_on"])

    def clean_attachment(self):
        f = self.cleaned_data.get("attachment")
        if f and hasattr(f, "size"):
            if Path(f.name).suffix.lower() not in FILE_TYPES:
                raise forms.ValidationError(_("Attach a PDF, JPG or PNG file."))
            if f.size > 5 * 1024 * 1024:
                raise forms.ValidationError(_("The file is larger than 5 MB."))
        return f

    def clean(self):
        data = super().clean()
        if data.get("expires_on") and data.get("publish_on") and data["expires_on"] < data["publish_on"]:
            self.add_error("expires_on", _("The last day is before the first day."))
        return data


class TemplateForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = ["name", "body", "is_active"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}
        labels = {"is_active": _("In use")}
