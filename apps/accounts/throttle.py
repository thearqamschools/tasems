"""Login lockout, counted from the audit log so it works across all server processes."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.core.models import AuditEvent


def _recent_failures():
    since = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    return AuditEvent.objects.filter(action=AuditEvent.Action.LOGIN_FAILED, occurred_at__gte=since)


def is_locked(username, ip):
    failures = _recent_failures()
    if username and failures.filter(object_repr__iexact=username).count() >= settings.LOGIN_MAX_FAILURES:
        return True
    if ip and failures.filter(ip_address=ip).count() >= settings.LOGIN_MAX_FAILURES_PER_IP:
        return True
    return False
