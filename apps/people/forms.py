import io
import json

from django import forms
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps

from apps.academics.models import ClassLevel, Section
from apps.core.phone import format_cnic, normalize_cnic, normalize_mobile
from apps.fees.models import DiscountType
from apps.fees.services import discount_at_admission

from .models import Certificate, Student
from .services import family_of, next_admission_no, save_student

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


# Classes that choose Biology or Computer.
PHOTO_MAX_BYTES = 5 * 1024 * 1024
SUBJECT_GROUP_CLASSES = {"pre-9", "class-9", "class-10"}
# Usual section names of every class (Setup → Classes and sections can use others).
SECTION_NAMES = ["Rose", "Jasmine", "Daisy", "Pansy", "Tulip"]
TEL = {"inputmode": "tel", "dir": "ltr", "placeholder": "0300-1234567"}
FAMILY = {
    "father": ["name", "phone", "occupation", "organisation"],  # no father email: the student's Email is used
    "mother": ["name", "phone", "occupation", "organisation"],
    "guardian": ["name", "phone", "relation_detail", "occupation"],
}


def section_order(name):
    """Rose, Jasmine, Daisy, Pansy, Tulip first, then any other names alphabetically."""
    return (SECTION_NAMES.index(name), "") if name in SECTION_NAMES else (len(SECTION_NAMES), name)


class StudentForm(forms.ModelForm):
    """One screen for a student, their class this session and their family."""

    roll_no = forms.IntegerField(required=False, min_value=1, label=_("Roll number"))
    class_level = forms.ModelChoiceField(queryset=ClassLevel.objects.none(), required=False, label=_("Class"))
    section_name = forms.ChoiceField(choices=[], required=False, label=_("Section"))

    father_name = forms.CharField(max_length=150, label=_("Father name"))
    father_phone = forms.CharField(max_length=20, label=_("Father mobile / WhatsApp"), widget=forms.TextInput(TEL))
    father_occupation = forms.CharField(max_length=100, required=False, label=_("Occupation"))
    father_organisation = forms.CharField(max_length=150, required=False, label=_("Organisation"))
    mother_name = forms.CharField(max_length=150, required=False, label=_("Mother name"))
    mother_phone = forms.CharField(
        max_length=20, required=False, label=_("Mother mobile / WhatsApp"), widget=forms.TextInput(TEL)
    )
    mother_occupation = forms.CharField(max_length=100, required=False, label=_("Occupation"))
    mother_organisation = forms.CharField(max_length=150, required=False, label=_("Organisation"))
    guardian_name = forms.CharField(max_length=150, required=False, label=_("Guardian name"))
    guardian_phone = forms.CharField(
        max_length=20, required=False, label=_("Guardian mobile / WhatsApp"), widget=forms.TextInput(TEL)
    )
    guardian_relation_detail = forms.CharField(
        max_length=60, required=False, label=_("Relationship"), help_text=_("e.g. uncle, aunt, grandfather")
    )
    guardian_occupation = forms.CharField(max_length=100, required=False, label=_("Occupation"))
    discount_type = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label=_("Discount"),
        empty_label=_("Full fee (no discount)"),
        help_text=_("A brother or sister (same father CNIC) gets the sibling fee by themselves; no need to choose it."),
    )

    class Meta:
        model = Student
        fields = [
            "admission_no",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "admission_date",
            "b_form_no",
            "father_cnic",
            "email",
            "current_address",
            "permanent_address",
            "is_hifz",
            "status",
            "subject_group",
            "reference",
            "notes",
            "photo",
        ]
        labels = {
            "admission_no": _("Admission number"),
            "first_name": _("First name"),
            "last_name": _("Last name"),
            "gender": _("Gender"),
            "date_of_birth": _("Date of birth"),
            "admission_date": _("Admission date"),
            "father_cnic": _("Father CNIC"),
            "email": _("Email"),
            "current_address": _("Current address"),
            "permanent_address": _("Permanent address"),
            "subject_group": _("Subject group"),
            "reference": _("Reference"),
            "notes": _("Notes"),
            "status": _("Status"),
            "photo": _("Photo"),
        }
        widgets = {
            "date_of_birth": DATE,
            "admission_date": DATE,
            "admission_no": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}),
            "b_form_no": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}),
            "father_cnic": forms.TextInput(
                attrs={"dir": "ltr", "inputmode": "numeric", "placeholder": "33100-1234567-1", "maxlength": 17}
            ),
            "email": forms.EmailInput(attrs={"dir": "ltr"}),
            "current_address": forms.Textarea(attrs={"rows": 2}),
            "permanent_address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "user"}),
        }

    def __init__(self, *args, branch, session, user=None, **kwargs):
        self.branch = branch
        self.session = session
        self.user = user
        super().__init__(*args, **kwargs)
        if self.instance.pk or user is None:
            del self.fields["discount_type"]  # later discounts: Fees → the student's fee account
        else:
            self.fields["discount_type"].queryset = DiscountType.objects.filter(is_active=True)
            self.fields["discount_type"].label_from_instance = lambda d: (
                f"{d.name} — {_('needs approval')}" if d.needs_approval else d.name
            )
        self.instance.branch = branch
        sections = (
            Section.objects.filter(branch=branch, session=session, is_active=True).select_related("class_level")
            if session
            else Section.objects.none()
        )
        self.sections = {(s.class_level_id, s.name.lower()): s for s in sections}
        by_class = {}
        for sec in sections:
            by_class.setdefault(str(sec.class_level_id), []).append(sec.name)
        names = sorted({s.name for s in sections}, key=section_order)
        self.fields["class_level"].queryset = ClassLevel.objects.filter(is_active=True)
        self.fields["class_level"].widget.attrs.update({"data-class-select": ""})
        self.fields["section_name"].choices = [("", "---------")] + [(n, n) for n in names]
        self.fields["section_name"].widget.attrs.update({"data-section-select": json.dumps(by_class)})
        group_classes = ClassLevel.objects.filter(code__in=SUBJECT_GROUP_CLASSES).values_list("id", flat=True)
        self.subject_group_classes = ",".join(str(i) for i in group_classes)
        if not session:
            self.fields["class_level"].help_text = _("No current session is set, so the class can be added later.")
        self.fields["admission_no"].help_text = _("Numbers only. The next free number is filled in for you.")
        if not self.instance.pk:
            self.fields.pop("status")
            self.initial.setdefault("admission_no", next_admission_no(branch))
        self.fields["father_cnic"].required = True
        self.initial["father_cnic"] = format_cnic(self.initial.get("father_cnic") or self.instance.father_cnic)
        # Typed with dashes (15 characters); stored as 13 digits after cleaning.
        self.fields["father_cnic"].max_length = 17
        self.fields["father_cnic"].widget.attrs["maxlength"] = 17  # the model's 13 would cut off a typed CNIC
        self.fields["father_cnic"].validators = []
        if self.instance.pk:
            for role, link in family_of(self.instance).items():
                g = link.guardian
                values = {
                    "name": g.full_name,
                    "phone": g.phone,
                    "occupation": g.occupation,
                    "organisation": g.organisation,
                    # Older records marked the contact "Other": show that as the guardian's relationship.
                    "relation_detail": link.relation_detail
                    or ("" if link.relationship == "guardian" else link.get_relationship_display()),
                }
                for field in FAMILY[role]:
                    self.initial.setdefault(f"{role}_{field}", values[field])
            if not self.initial.get("father_name"):
                self.initial["father_name"] = self.instance.father_name

    def clean_photo(self):
        """A passport-size photo: any common image, made a small JPEG (for the profile and ID card)."""
        photo = self.cleaned_data.get("photo")
        if not photo or photo == self.instance.photo or getattr(photo, "size", None) is None:
            return photo
        if photo.size > PHOTO_MAX_BYTES:
            raise forms.ValidationError(_("The photo is larger than 5 MB."))
        try:
            image = Image.open(photo)
            image = ImageOps.exif_transpose(image).convert("RGB")
        except (OSError, ValueError) as error:
            raise forms.ValidationError(_("This file is not a photo (use JPG or PNG).")) from error
        image.thumbnail((600, 600))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=85)
        return ContentFile(out.getvalue(), name="photo.jpg")

    def clean_admission_no(self):
        value = self.cleaned_data["admission_no"].strip()
        unchanged = self.instance.pk and value == self.instance.admission_no  # older records may have letters
        if not value.isdigit() and not unchanged:
            raise forms.ValidationError(_("Use numbers only, e.g. 4256."))
        clash = Student.objects.filter(branch=self.branch, admission_no=value).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(_("This admission number is already used in this branch."))
        return value

    def clean_father_cnic(self):
        raw = self.cleaned_data.get("father_cnic", "").strip()
        cnic = normalize_cnic(raw)
        if cnic is None:
            raise forms.ValidationError(_("A CNIC has 13 digits, e.g. 33100-1234567-1."))
        return cnic

    def _mobile(self, field):
        raw = self.cleaned_data.get(field, "").strip()
        if not raw:
            return ""
        phone = normalize_mobile(raw)
        if phone is None:
            raise forms.ValidationError(_("Enter a Pakistani mobile number, e.g. 0300-1234567."))
        return phone

    def clean_father_phone(self):
        return self._mobile("father_phone")

    def clean_mother_phone(self):
        return self._mobile("mother_phone")

    def clean_guardian_phone(self):
        return self._mobile("guardian_phone")

    def clean(self):
        data = super().clean()
        for role in ("mother", "guardian"):
            if data.get(f"{role}_name") and not data.get(f"{role}_phone") and f"{role}_phone" not in self.errors:
                self.add_error(f"{role}_phone", _("Enter a mobile number for this person."))
            if data.get(f"{role}_phone") and not data.get(f"{role}_name"):
                self.add_error(f"{role}_name", _("Enter this person's name."))
        if data.get("father_name"):
            self.instance.father_name = data["father_name"]

        level, name = data.get("class_level"), data.get("section_name")
        data["section"] = None
        if level and not name:
            self.add_error("section_name", _("Choose the section."))
        elif name and not level:
            self.add_error("class_level", _("Choose the class."))
        elif level and name:
            section = self.sections.get((level.id, name.lower()))
            if section is None:
                self.add_error(
                    "section_name",
                    _("%(c)s has no section %(s)s this session. Add it in Setup → Classes and sections.")
                    % {"c": level, "s": name},
                )
            else:
                data["section"] = section
                gender = data.get("gender")
                if gender and section.gender_group != "mixed":
                    if {"boys": "male", "girls": "female"}[section.gender_group] != gender:
                        self.add_error(
                            "section_name",
                            _("This section is for %(g)s only.") % {"g": section.get_gender_group_display()},
                        )
        if level and level.code in SUBJECT_GROUP_CLASSES:
            if not data.get("subject_group"):
                self.add_error("subject_group", _("Choose Biology or Computer."))
        else:
            data["subject_group"] = ""
            self.instance.subject_group = ""
        return data

    def family(self):
        d = self.cleaned_data
        return {role: {field: d.get(f"{role}_{field}", "") for field in fields} for role, fields in FAMILY.items()}

    @transaction.atomic
    def save_all(self):
        """Saves the student, their family, their class this session and the discount chosen at admission."""
        data = self.cleaned_data
        student = save_student(
            self.save(commit=False),
            session=self.session,
            section=data.get("section"),
            roll_no=data.get("roll_no"),
            family=self.family(),
        )
        if data.get("discount_type"):
            discount_at_admission(student, data["discount_type"], self.user)
        return student


class LeaveForm(forms.Form):
    status = forms.ChoiceField(
        choices=[(v, label) for v, label in Student.Status.choices if v != Student.Status.ACTIVE],
        label=_("Leaving as"),
    )
    left_on = forms.DateField(label=_("Date of leaving"), widget=DATE)
    reason = forms.CharField(max_length=200, required=False, label=_("Reason"))
    certificate = forms.BooleanField(required=False, initial=True, label=_("Issue a school leaving certificate"))
    conduct = forms.ChoiceField(choices=Certificate.Conduct.choices, initial="good", label=_("Conduct"))
    dues_cleared = forms.BooleanField(required=False, label=_("Fee dues are cleared"))

    def clean_left_on(self):
        value = self.cleaned_data["left_on"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("The date is in the future."))
        return value


class CertificateForm(forms.Form):
    conduct = forms.ChoiceField(choices=Certificate.Conduct.choices, initial="good", label=_("Conduct"))
    remarks = forms.CharField(max_length=200, required=False, label=_("Remarks (optional)"))
