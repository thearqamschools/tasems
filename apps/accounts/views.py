"""Staff sign-in: password first, then two-factor for privileged roles."""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render, resolve_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import mfa
from .forms import CodeForm, LoginForm
from .middleware import MFA_SESSION_KEY
from .models import User
from .throttle import is_locked

PENDING_KEY = "pending_login"
PENDING_SECONDS = 300
MAX_CODE_ATTEMPTS = 5


def _next_url(request):
    url = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return resolve_url(settings.LOGIN_REDIRECT_URL)


def _resolve_username(identifier):
    """Staff may sign in with a mobile number (e.g. 0300-1234567) instead of a username."""
    identifier = identifier.strip()
    compact = identifier.replace("-", "").replace(" ", "").lstrip("+")
    if compact.isdigit() and len(compact) >= 10:
        match = User.objects.filter(phone__endswith=compact[-10:], is_active=True)
        if match.count() == 1:
            return match.get().username
    return identifier


def _complete_login(request, user, backend):
    login(request, user, backend=backend)
    request.session[MFA_SESSION_KEY] = True
    request.session.pop(PENDING_KEY, None)
    translation.activate(user.preferred_language)


def _with_language(response, user):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user.preferred_language, samesite="Lax")
    return response


def _finish_login(request, user, backend, next_url):
    _complete_login(request, user, backend)
    return _with_language(redirect(next_url), user)


def _pending(request):
    data = request.session.get(PENDING_KEY)
    if not data or time.time() - data["at"] > PENDING_SECONDS:
        request.session.pop(PENDING_KEY, None)
        return None, None
    user = User.objects.filter(pk=data["user_id"], is_active=True).first()
    return user, data


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_next_url(request))
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = _resolve_username(form.cleaned_data["identifier"])
        ip = request.META.get("REMOTE_ADDR")
        if is_locked(username, ip):
            form.add_error(None, _("Too many failed attempts. Please wait 15 minutes and try again."))
        else:
            user = authenticate(request, username=username, password=form.cleaned_data["password"])
            if user is None:
                form.add_error(None, _("Username or password is incorrect."))
            elif not user.requires_mfa:
                return _finish_login(request, user, user.backend, _next_url(request))
            else:
                request.session[PENDING_KEY] = {
                    "user_id": user.pk,
                    "backend": user.backend,
                    "at": time.time(),
                    "next": _next_url(request),
                    "attempts": 0,
                }
                if mfa.has_confirmed_device(user):
                    return redirect("accounts:verify")
                return redirect("accounts:mfa_setup")
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


@never_cache
def verify_view(request):
    user, data = _pending(request)
    if user is None:
        messages.info(request, _("Please sign in again."))
        return redirect("accounts:login")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if mfa.verify(user, form.cleaned_data["code"]):
            return _finish_login(request, user, data["backend"], data["next"])
        data["attempts"] += 1
        request.session[PENDING_KEY] = data
        if data["attempts"] >= MAX_CODE_ATTEMPTS:
            request.session.pop(PENDING_KEY, None)
            messages.error(request, _("Too many wrong codes. Please sign in again."))
            return redirect("accounts:login")
        form.add_error("code", _("This code is not correct. Check the time on your phone and try again."))
    return render(request, "accounts/verify.html", {"form": form})


@never_cache
def mfa_setup_view(request):
    user, data = _pending(request)
    if user is None:
        return redirect("accounts:login")
    secret = request.session.get("mfa_setup_secret") or mfa.new_secret()
    request.session["mfa_setup_secret"] = secret
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        step = mfa.check_secret(secret, form.cleaned_data["code"])
        if step is not None:
            codes = mfa.confirm_device(user, secret, step)
            request.session.pop("mfa_setup_secret", None)
            _complete_login(request, user, data["backend"])
            response = render(request, "accounts/recovery_codes.html", {"codes": codes, "next": data["next"]})
            return _with_language(response, user)
        form.add_error("code", _("This code is not correct. Scan the QR code again and enter the new code."))
    uri = mfa.provisioning_uri(user, secret)
    return render(
        request,
        "accounts/mfa_setup.html",
        {"form": form, "qr_svg": mfa.qr_svg(uri), "secret": secret, "user_obj": user},
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def admin_login_redirect(request, extra_context=None):
    """The admin site uses the same sign-in (and two-factor) as everything else."""
    return redirect(f"/accounts/login/?next={request.GET.get('next', '/admin/')}")
