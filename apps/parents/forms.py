from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from apps.core.phone import normalize_mobile

PHONE = forms.TextInput(
    attrs={"inputmode": "tel", "dir": "ltr", "autocomplete": "username", "placeholder": "0300-1234567"}
)


class MobileField(forms.CharField):
    def clean(self, value):
        value = super().clean(value)
        phone = normalize_mobile(value)
        if phone is None:
            raise forms.ValidationError(_("Enter your mobile number, e.g. 0300-1234567."))
        return phone


class ParentLoginForm(forms.Form):
    phone = MobileField(label=_("Mobile number"), max_length=20, widget=PHONE)
    password = forms.CharField(
        label=_("Password"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )


class NewPasswordMixin(forms.Form):
    password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("At least 10 characters, not only numbers."),
    )
    password2 = forms.CharField(
        label=_("New password again"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("The two passwords are not the same."))
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return data


class StartForm(NewPasswordMixin):
    phone = MobileField(label=_("Mobile number"), max_length=20, widget=PHONE)
    code = forms.CharField(
        label=_("Access code from the school"),
        max_length=12,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr", "autocomplete": "one-time-code"}),
    )
    field_order = ["phone", "code", "password1", "password2"]

    def clean_code(self):
        return "".join(ch for ch in self.cleaned_data["code"] if ch.isdigit())


class ChangePasswordForm(NewPasswordMixin):
    current = forms.CharField(
        label=_("Current password"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )
    field_order = ["current", "password1", "password2"]
