"""Two-factor login with an authenticator app (Google Authenticator, Microsoft Authenticator, etc.)."""

import io
import secrets

import pyotp
import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.core.crypto import decrypt, encrypt

from .models import MFADevice, RecoveryCode

RECOVERY_CODE_COUNT = 8


def new_secret():
    return pyotp.random_base32()


def provisioning_uri(user, secret):
    return pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=settings.MFA_ISSUER)


def qr_svg(uri):
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()


def _clean(code):
    return "".join(ch for ch in str(code) if ch.isalnum()).upper()


def _matching_step(totp, code, after_step=0):
    now_step = int(timezone.now().timestamp()) // totp.interval
    for step in (now_step - 1, now_step, now_step + 1):
        if step > after_step and totp.at(step * totp.interval) == code:
            return step
    return None


def check_secret(secret, code):
    """Used during setup, before the device is saved. Returns the matched time step or None."""
    return _matching_step(pyotp.TOTP(secret), _clean(code))


@transaction.atomic
def confirm_device(user, secret, used_step):
    """Saves the device; the code used to confirm it can never be used to sign in."""
    MFADevice.objects.update_or_create(
        user=user,
        defaults={"secret_encrypted": encrypt(secret), "confirmed_at": timezone.now(), "last_used_step": used_step},
    )
    return new_recovery_codes(user)


def new_recovery_codes(user):
    RecoveryCode.objects.filter(user=user).delete()
    codes = [secrets.token_hex(5).upper() for _ in range(RECOVERY_CODE_COUNT)]
    RecoveryCode.objects.bulk_create([RecoveryCode(user=user, code_hash=make_password(c)) for c in codes])
    return [f"{c[:5]}-{c[5:]}" for c in codes]


def has_confirmed_device(user):
    return MFADevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


@transaction.atomic
def verify(user, code):
    """True if `code` is a current authenticator code (not reused) or an unused recovery code."""
    code = _clean(code)
    device = MFADevice.objects.select_for_update().filter(user=user, confirmed_at__isnull=False).first()
    if device and code.isdigit() and len(code) == 6:
        step = _matching_step(pyotp.TOTP(decrypt(device.secret_encrypted)), code, device.last_used_step)
        if step is None:
            return False
        device.last_used_step = step
        device.save(update_fields=["last_used_step", "updated_at"])
        return True
    for recovery in RecoveryCode.objects.select_for_update().filter(user=user, used_at__isnull=True):
        if check_password(code, recovery.code_hash):
            recovery.used_at = timezone.now()
            recovery.save(update_fields=["used_at"])
            return True
    return False
