"""Sign-in, lockout and two-step check."""

import re

import pyotp
import pytest

from apps.accounts.models import Scope
from apps.core.crypto import decrypt

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng-pass-123"


def sign_in(client, identifier, password=PASSWORD):
    return client.post("/accounts/login/", {"identifier": identifier, "password": password})


def test_teacher_signs_in_without_two_step(client, org, make_user):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    response = sign_in(client, teacher.username)
    assert response.status_code == 302 and response["Location"] == "/"
    assert client.get("/").status_code == 200


def test_sign_in_with_mobile_number(client, org, make_user):
    make_user("class_teacher", Scope.BRANCH, org["samanabad"], phone="03001234567")
    assert sign_in(client, "0300-1234567")["Location"] == "/"


def test_wrong_password_is_refused(client, org, make_user):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    response = sign_in(client, teacher.username, "wrong")
    assert "incorrect" in response.content.decode()
    assert client.get("/")["Location"].startswith("/accounts/login/")


def test_lockout_after_five_failures(client, org, make_user):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    for _ in range(5):
        sign_in(client, teacher.username, "wrong")
    response = sign_in(client, teacher.username)  # correct password, but locked
    assert "Too many failed attempts" in response.content.decode()


def test_principal_must_set_up_two_step(client, org, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    assert sign_in(client, principal.username)["Location"] == "/accounts/two-factor/setup/"
    assert client.get("/")["Location"].startswith("/accounts/login/")  # not signed in yet

    page = client.get("/accounts/two-factor/setup/")
    assert "<svg" in page.content.decode()
    secret = client.session["mfa_setup_secret"]
    response = client.post("/accounts/two-factor/setup/", {"code": pyotp.TOTP(secret).now()})
    codes = re.findall(r"<span>([0-9A-F]{5}-[0-9A-F]{5})</span>", response.content.decode())
    assert len(codes) == 8
    assert client.get("/").status_code == 200
    assert decrypt(principal.mfa_device.secret_encrypted) == secret
    assert principal.mfa_device.secret_encrypted != secret  # stored encrypted


def _principal_with_device(client, org, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    sign_in(client, principal.username)
    client.get("/accounts/two-factor/setup/")
    secret = client.session["mfa_setup_secret"]
    response = client.post("/accounts/two-factor/setup/", {"code": pyotp.TOTP(secret).now()})
    codes = re.findall(r"<span>([0-9A-F]{5}-[0-9A-F]{5})</span>", response.content.decode())
    client.post("/accounts/logout/")
    return principal, secret, codes


def test_verify_code_and_block_reuse(client, org, make_user):
    principal, secret, _codes = _principal_with_device(client, org, make_user)
    assert sign_in(client, principal.username)["Location"] == "/accounts/verify/"
    bad = client.post("/accounts/verify/", {"code": "000000"})
    assert "not correct" in bad.content.decode()
    # The code used during setup cannot be used again.
    used = pyotp.TOTP(secret).now()
    response = client.post("/accounts/verify/", {"code": used})
    assert response.status_code == 200 and "not correct" in response.content.decode()


def test_backup_code_works_once(client, org, make_user):
    principal, _secret, codes = _principal_with_device(client, org, make_user)
    sign_in(client, principal.username)
    assert client.post("/accounts/verify/", {"code": codes[0]})["Location"] == "/"
    client.post("/accounts/logout/")
    sign_in(client, principal.username)
    assert client.post("/accounts/verify/", {"code": codes[0]}).status_code == 200  # refused


def test_session_without_two_step_is_signed_out(client, org, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    client.force_login(principal)  # e.g. role given after sign-in
    assert client.get("/")["Location"].startswith("/accounts/login/")


def test_admin_uses_the_same_sign_in(client):
    assert client.get("/admin/login/?next=/admin/")["Location"].startswith("/accounts/login/")


def test_urdu_pages_are_right_to_left(org, make_user, login_as):
    client = login_as(make_user("class_teacher", Scope.BRANCH, org["samanabad"]))
    client.post("/i18n/setlang/", {"language": "ur", "next": "/"})
    body = client.get("/").content.decode()
    assert 'dir="rtl"' in body and 'lang="ur"' in body
