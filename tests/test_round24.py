"""Round 23–24 (project lead, 28 Nov 2026): full subject names on result cards; the Windows copy online through a
Cloudflare Tunnel — the visitor's real address, https-only cookies online, start with Windows, a daily backup."""

import importlib.util
from pathlib import Path

import pytest
from django.conf import settings
from django.test import RequestFactory

from apps.core.net import client_ip

ROOT = Path(settings.BASE_DIR)


def _req(remote, cf=None):
    meta = {"REMOTE_ADDR": remote}
    if cf is not None:
        meta["HTTP_CF_CONNECTING_IP"] = cf
    return RequestFactory().get("/", **meta)


def test_visitor_address_comes_from_cloudflare_only_through_the_tunnel(settings):
    settings.CLOUDFLARE_TUNNEL = True
    assert client_ip(_req("127.0.0.1", "203.0.113.7")) == "203.0.113.7"
    assert client_ip(_req("192.168.1.20", "203.0.113.7")) == "192.168.1.20"  # office computer cannot pretend
    assert client_ip(_req("127.0.0.1", "not-an-ip")) == "127.0.0.1"
    settings.CLOUDFLARE_TUNNEL = False
    assert client_ip(_req("127.0.0.1", "203.0.113.7")) == "127.0.0.1"
    assert client_ip(None) is None


@pytest.mark.django_db
def test_cookies_https_only_when_opened_through_https(client):
    secure = client.get("/accounts/login/", secure=True)
    assert secure.cookies["csrftoken"]["secure"] is True
    plain = client.get("/accounts/login/")
    assert plain.status_code == 200


def test_result_card_has_full_subject_names_hand_sheet_short():
    card = (ROOT / "templates" / "exams" / "exam_card_document.html").read_text()
    assert "p.subject.name" in card and "subject.short" not in card


def _launcher():
    spec = importlib.util.spec_from_file_location("launcher", ROOT / "windows" / "launcher.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_daily_backups_keep_the_last_thirty(tmp_path):
    launcher = _launcher()
    for day in range(1, 41):
        (tmp_path / f"tasems-daily-2026-10-{day:02d}.dump").write_text("x") if day <= 31 else (
            tmp_path / f"tasems-daily-2026-11-{day - 31:02d}.dump"
        ).write_text("x")
    (tmp_path / "tasems-2026-11-28_0900.dump").write_text("hand-made")  # a backup made by hand is never deleted
    launcher.prune(tmp_path)
    assert len(list(tmp_path.glob("tasems-daily-*.dump"))) == launcher.KEEP_DAILY
    assert (tmp_path / "tasems-2026-11-28_0900.dump").exists()
    assert not (tmp_path / "tasems-daily-2026-10-01.dump").exists()


def test_installer_starts_tasems_with_windows():
    nsi = (ROOT / "windows" / "installer.nsi").read_text()
    assert "$SMSTARTUP\\TASEMS.lnk" in nsi and "--autostart" in nsi
