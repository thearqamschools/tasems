from django import forms
from django.db.models import Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Section
from apps.accounts.models import Role, Scope, User
from apps.core.phone import normalize_mobile
from apps.fees.models import BankAccount, BranchFeeSettings, DiscountType, FeeRate
from apps.organisation.models import AcademicSession, Branch, Campus, HeadOffice, Region
from apps.people.forms import SECTION_NAMES

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
UR = forms.TextInput(attrs={"dir": "rtl", "lang": "ur", "class": "ur"})
LTR = forms.TextInput(attrs={"dir": "ltr"})


LABELS = {
    "class_level": _("Class"),
    "name": _("Name"),
    "gender_group": _("Boys / girls"),
    "campus": _("Campus"),
    "class_teacher": _("Class teacher"),
    "capacity": _("Capacity"),
    "is_active": _("In use"),
    "address": _("Address"),
    "head": _("Fee"),
    "amount": _("Amount (Rs)"),
    "sibling_amount": _("Brothers and sisters (Rs)"),
    "effective_from": _("From month"),
    "due_day": _("Last day to pay"),
    "late_fine": _("Late fine (Rs)"),
    "allow_partial_payment": _("Allow part payments"),
    "bank_name": _("Bank"),
    "bank_branch": _("Bank branch"),
    "account_title": _("Account title"),
    "account_number": _("Account number"),
    "receipt_whatsapp": _("Receipts on WhatsApp"),
    "voucher_note": _("Note on voucher"),
    "print_back_side": _("Print the back side"),
    "back_title": _("Back side title"),
    "code": _("Code"),
    "head_office": _("Head office"),
    "region": _("Region"),
    "ownership": _("Ownership"),
    "royalty_percent": _("Royalty %"),
    "city": _("City"),
    "phone": _("Phone"),
    "starts_on": _("Starts"),
    "ends_on": _("Ends"),
}


class Labelled:
    """Plain, translated labels (model field names are English-only)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in LABELS:
                field.label = LABELS[name]


def staff_of(branch):
    """People with an active role covering this branch (class teacher choices)."""
    cond = (
        Q(role_assignments__branch=branch)
        | Q(role_assignments__head_office_id=branch.head_office_id)
        | Q(role_assignments__scope=Scope.NETWORK)
    )
    if branch.region_id:
        cond |= Q(role_assignments__region_id=branch.region_id)
    return (
        User.objects.filter(cond, is_active=True, role_assignments__is_active=True)
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


BANK_SUGGESTIONS = ["Askari Bank", "Bank Alfalah", "JazzCash", "Easypaisa", "UBL", "HBL", "MCB", "Meezan Bank"]


class SuggestInput(forms.TextInput):
    """A text box that offers a list of usual values (the person can still type another)."""

    def __init__(self, suggestions, attrs=None):
        super().__init__(attrs)
        self.suggestions = suggestions

    def render(self, name, value, attrs=None, renderer=None):
        list_id = f"{(attrs or {}).get('id', name)}-suggestions"
        html = super().render(name, value, {**(attrs or {}), "list": list_id, "autocomplete": "off"}, renderer)
        options = "".join(format_html('<option value="{}">', s) for s in self.suggestions)
        return mark_safe(f'{html}<datalist id="{list_id}">{options}</datalist>')  # noqa: S308 (escaped above)


class SectionForm(Labelled, forms.ModelForm):
    class Meta:
        model = Section
        fields = ["class_level", "name", "gender_group", "campus", "class_teacher", "capacity", "is_active"]
        widgets = {"name": SuggestInput(SECTION_NAMES)}

    def __init__(self, *args, branch, session, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch, self.instance.session = branch, session
        self.fields["campus"].queryset = Campus.objects.filter(branch=branch, is_active=True)
        self.fields["class_teacher"].queryset = staff_of(branch)
        self.fields["class_teacher"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean(self):
        data = super().clean()
        level, name = data.get("class_level"), data.get("name")
        if level and name:
            clash = Section.objects.filter(
                branch=self.instance.branch, session=self.instance.session, class_level=level, name__iexact=name
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error("name", _("This class already has a section with this name in this session."))
        return data


class CampusForm(Labelled, forms.ModelForm):
    class Meta:
        model = Campus
        fields = ["name", "gender_group", "address", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch

    def clean_name(self):
        name = self.cleaned_data["name"]
        clash = Campus.objects.filter(branch=self.instance.branch, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(_("This branch already has a campus with this name."))
        return name


class FeeRateForm(Labelled, forms.ModelForm):
    class Meta:
        model = FeeRate
        fields = ["head", "class_level", "amount", "sibling_amount", "effective_from"]
        widgets = {"effective_from": DATE}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["head"].queryset = self.fields["head"].queryset.filter(is_active=True)
        self.fields["class_level"].queryset = self.fields["class_level"].queryset.filter(is_active=True)

    def clean_effective_from(self):
        day = self.cleaned_data["effective_from"]
        return day.replace(day=1)  # rates apply from the first of a month

    def clean(self):
        data = super().clean()
        head, level, start = data.get("head"), data.get("class_level"), data.get("effective_from")
        if head and start:
            clash = FeeRate.objects.filter(
                branch=self.instance.branch, head=head, class_level=level, effective_from=start
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error("effective_from", _("A rate for this fee and class already starts in this month."))
        return data


class FeeSettingsForm(Labelled, forms.ModelForm):
    class Meta:
        model = BranchFeeSettings
        fields = [
            "due_day",
            "late_fine",
            "allow_partial_payment",
            "bank_name",
            "bank_branch",
            "account_title",
            "account_number",
            "receipt_whatsapp",
            "voucher_note",
            "print_back_side",
            "back_title",
            "back_notes_en",
            "back_notes_ur",
            "back_footer_ur",
        ]
        widgets = {
            "account_number": LTR,
            "receipt_whatsapp": LTR,
            "back_notes_en": forms.Textarea(attrs={"rows": 4}),
            "back_notes_ur": forms.Textarea(attrs={"rows": 4, "dir": "rtl", "lang": "ur", "class": "ur"}),
            "back_footer_ur": UR,
        }


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ["name", "account_title", "account_number", "sort_order", "is_active"]
        labels = {
            "name": _("Bank or wallet"),
            "account_title": _("Account title"),
            "account_number": _("Account number"),
            "sort_order": _("Order in lists"),
            "is_active": _("In use"),
        }
        widgets = {"account_number": LTR, "name": SuggestInput(BANK_SUGGESTIONS)}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = BankAccount.objects.filter(branch=self.instance.branch, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(_("This branch already has this bank."))
        return name


class DiscountTypeForm(forms.ModelForm):
    class Meta:
        model = DiscountType
        fields = ["name", "percent", "needs_approval", "sort_order", "is_active"]
        labels = {
            "name": _("Name"),
            "percent": _("Discount %"),
            "needs_approval": _("Needs approval"),
            "sort_order": _("Order in lists"),
            "is_active": _("In use"),
        }


class BranchForm(Labelled, forms.ModelForm):
    class Meta:
        model = Branch
        fields = [
            "code",
            "name",
            "head_office",
            "region",
            "ownership",
            "royalty_percent",
            "city",
            "city_code",
            "is_head_office",
            "address",
            "phone",
            "reference_prefix",
            "is_active",
        ]
        widgets = {
            "code": LTR,
            "phone": LTR,
            "reference_prefix": LTR,
            "city_code": LTR,
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, head_offices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head_office"].queryset = HeadOffice.objects.filter(id__in=[h.id for h in head_offices])
        self.fields["region"].queryset = Region.objects.filter(head_office__in=head_offices, is_active=True)

    def clean(self):
        data = super().clean()
        region, office = data.get("region"), data.get("head_office")
        if region and office and region.head_office_id != office.id:
            self.add_error("region", _("This region belongs to another head office."))
        return data


class RegionForm(Labelled, forms.ModelForm):
    class Meta:
        model = Region
        fields = ["head_office", "code", "name", "is_active"]
        widgets = {"code": LTR}

    def __init__(self, *args, head_offices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head_office"].queryset = HeadOffice.objects.filter(id__in=[h.id for h in head_offices])


class SessionForm(Labelled, forms.ModelForm):
    class Meta:
        model = AcademicSession
        fields = ["name", "starts_on", "ends_on"]
        widgets = {"starts_on": DATE, "ends_on": DATE, "name": forms.TextInput(attrs={"placeholder": "2027-28"})}

    def clean(self):
        data = super().clean()
        if data.get("starts_on") and data.get("ends_on") and data["ends_on"] <= data["starts_on"]:
            self.add_error("ends_on", _("The session must end after it starts."))
        return data


class AssignmentForm(forms.Form):
    """Give someone a role at a scope. Whether it is allowed is decided by apps.setup.access."""

    role = forms.ModelChoiceField(queryset=Role.objects.none(), label=_("Role"))
    scope = forms.ChoiceField(choices=Scope.choices, label=_("Where"))
    head_office = forms.ModelChoiceField(queryset=HeadOffice.objects.none(), required=False, label=_("Head office"))
    region = forms.ModelChoiceField(queryset=Region.objects.none(), required=False, label=_("Region"))
    branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=False, label=_("Branch"))
    starts_on = forms.DateField(required=False, widget=DATE, label=_("From"))
    ends_on = forms.DateField(required=False, widget=DATE, label=_("Until"), help_text=_("Leave empty if open-ended."))

    def __init__(self, *args, roles, targets, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.filter(id__in=[r.id for r in roles])
        self.fields["role"].label_from_instance = lambda r: r.display_name
        self.fields["head_office"].queryset = HeadOffice.objects.filter(id__in=[h.id for h in targets["head_offices"]])
        self.fields["region"].queryset = Region.objects.filter(id__in=[r.id for r in targets["regions"]])
        self.fields["branch"].queryset = Branch.objects.filter(id__in=[b.id for b in targets["branches"]])
        scopes = [(Scope.BRANCH.value, Scope.BRANCH.label)]
        if targets["regions"]:
            scopes.insert(0, (Scope.REGION.value, Scope.REGION.label))
        if targets["head_offices"]:
            scopes.insert(0, (Scope.HEAD_OFFICE.value, Scope.HEAD_OFFICE.label))
        if targets["network"]:
            scopes.insert(0, (Scope.NETWORK.value, Scope.NETWORK.label))
        self.fields["scope"].choices = scopes

    def clean(self):
        data = super().clean()
        scope = data.get("scope")
        need = {Scope.HEAD_OFFICE: "head_office", Scope.REGION: "region", Scope.BRANCH: "branch"}.get(scope)
        if need and not data.get(need):
            self.add_error(need, _("Choose where this role applies."))
        for other in ("head_office", "region", "branch"):
            if other != need:
                data[other] = None
        if data.get("starts_on") and data.get("ends_on") and data["ends_on"] < data["starts_on"]:
            self.add_error("ends_on", _("End date is before start date."))
        return data


class NewUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "phone", "email", "preferred_language"]
        widgets = {
            "username": forms.TextInput(attrs={"dir": "ltr", "autocomplete": "off"}),
            "phone": forms.TextInput(attrs={"dir": "ltr", "inputmode": "tel", "placeholder": "0300-1234567"}),
            "email": forms.EmailInput(attrs={"dir": "ltr"}),
        }

    LABELS = {
        "username": _("Username"),
        "first_name": _("First name"),
        "last_name": _("Last name"),
        "phone": _("Mobile"),
        "email": _("Email"),
        "preferred_language": _("Language"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = self.LABELS[name]
        self.fields["first_name"].required = True
        if "username" in self.fields:
            self.fields["username"].help_text = _("Letters, digits and @ . + - _ only.")

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not phone:
            return ""
        normal = normalize_mobile(phone)
        if not normal:
            raise forms.ValidationError(_("Enter an 11-digit mobile number, e.g. 0300-1234567."))
        # Sign-in by mobile matches the last 10 digits (accounts.views), so check duplicates the same way.
        if User.objects.filter(phone__endswith=normal[-10:]).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Another login already uses this mobile number."))
        return normal


class UserDetailsForm(NewUserForm):
    class Meta(NewUserForm.Meta):
        fields = ["first_name", "last_name", "phone", "email", "preferred_language"]
