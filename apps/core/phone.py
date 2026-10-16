"""Pakistani mobile numbers, stored one way: 03XXXXXXXXX (11 digits)."""

import re


def normalize_mobile(value):
    """Return 03XXXXXXXXX, or None if the value is not a Pakistani mobile number.

    Accepts 0300-1234567, 0300 1234567, +92 300 1234567, 923001234567, 3001234567.
    """
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("3"):
        digits = "0" + digits
    if len(digits) == 11 and digits.startswith("03"):
        return digits
    return None


def normalize_cnic(value):
    """Return the 13 digits of a CNIC (35202-1234567-1 → 3520212345671), or None if it is not one."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 13 else None


def format_cnic(digits):
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}" if digits and len(digits) == 13 else digits or ""
