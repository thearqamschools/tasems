"""The visitor's address, also when TASEMS is online through a Cloudflare Tunnel (R24-1, project lead 28 Nov 2026).

Through the tunnel every request reaches TASEMS from the tunnel program on the same computer (127.0.0.1); the
visitor's own address comes in Cloudflare's CF-Connecting-IP header. It is trusted only when the Windows copy is set
up for the tunnel (PUBLIC_URL in its config.env) and the request really comes from this computer — so a computer on
the office network cannot pretend to be someone else."""

import ipaddress

from django.conf import settings

LOCAL = {"127.0.0.1", "::1"}


def client_ip(request):
    if request is None:
        return None
    remote = request.META.get("REMOTE_ADDR")
    if getattr(settings, "CLOUDFLARE_TUNNEL", False) and remote in LOCAL:
        forwarded = request.META.get("HTTP_CF_CONNECTING_IP", "").strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return remote


class SecureCookiesOverHttpsMiddleware:
    """On the office network TASEMS is plain http (cookies cannot be https-only there); opened online through https,
    the sign-in and form cookies are marked https-only (R24-2)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.is_secure():
            for name in (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME, settings.LANGUAGE_COOKIE_NAME):
                if name in response.cookies:
                    response.cookies[name]["secure"] = True
        return response
