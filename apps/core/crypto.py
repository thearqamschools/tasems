"""Encryption for secrets stored in the database (e.g. two-factor keys).

The key comes from the FIELD_ENCRYPTION_KEY environment variable, never from code.
Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet():
    key = settings.FIELD_ENCRYPTION_KEY.encode()
    try:
        return Fernet(key)
    except ValueError:
        # Hosting panels generate random strings that are not Fernet keys; derive one from it.
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
