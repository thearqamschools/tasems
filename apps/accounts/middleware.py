"""Blocks any signed-in session that should have passed two-factor login but did not
(for example a role with two-factor added after the person signed in)."""

from django.contrib.auth import logout
from django.shortcuts import redirect

MFA_SESSION_KEY = "mfa_verified"
EXEMPT_PREFIXES = ("/accounts/", "/static/", "/i18n/", "/healthz")


class MFAEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not request.path.startswith(EXEMPT_PREFIXES)
            and not request.session.get(MFA_SESSION_KEY)
            and user.requires_mfa
        ):
            logout(request)
            return redirect(f"/accounts/login/?next={request.path}")
        return self.get_response(request)
