from django import forms
from django.utils.translation import gettext_lazy as _


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label=_("Username or mobile number"),
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True, "dir": "ltr"}),
    )
    password = forms.CharField(
        label=_("Password"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "dir": "ltr"})
    )


class CodeForm(forms.Form):
    code = forms.CharField(
        label=_("6-digit code"),
        max_length=20,
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "numeric", "autofocus": True, "dir": "ltr"}
        ),
        help_text=_("Open your authenticator app. Lost your phone? Enter a backup code instead."),
    )
