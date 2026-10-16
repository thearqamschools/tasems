"""Automatic audit trail for registered models.

Usage: decorate a model class with `@audited` (or call `register(Model)`).
Every create, update and delete is written to AuditEvent with before/after values.
"""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .middleware import get_current_request
from .models import AuditEvent

SKIP_FIELDS = {"password", "updated_at", "created_at", "last_login"}
_registered = set()


def _snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in SKIP_FIELDS:
            continue
        value = getattr(instance, field.attname)
        data[field.attname] = value if isinstance(value, (int, float, bool, type(None))) else str(value)
    return data


def _request_context():
    request = get_current_request()
    if request is None:
        return None, None
    user = getattr(request, "user", None)
    actor = user if user is not None and user.is_authenticated else None
    ip = request.META.get("REMOTE_ADDR")
    return actor, ip


def _write(action, instance, changes):
    actor, ip = _request_context()
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        model_label=instance._meta.label,
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        branch_id=getattr(instance, "branch_id", None),
        changes=changes,
        ip_address=ip,
    )


def _pre_save(sender, instance, **kwargs):
    instance._audit_before = None
    if instance.pk:
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old is not None:
            instance._audit_before = _snapshot(old)


def _post_save(sender, instance, created, **kwargs):
    after = _snapshot(instance)
    if created:
        _write(AuditEvent.Action.CREATE, instance, {"after": after})
        return
    before = getattr(instance, "_audit_before", None) or {}
    diff = {k: {"from": before.get(k), "to": v} for k, v in after.items() if before.get(k) != v}
    if diff:
        _write(AuditEvent.Action.UPDATE, instance, diff)


def _post_delete(sender, instance, **kwargs):
    _write(AuditEvent.Action.DELETE, instance, {"before": _snapshot(instance)})


def register(model):
    if model in _registered:
        return model
    pre_save.connect(_pre_save, sender=model, dispatch_uid=f"audit_pre_{model._meta.label}")
    post_save.connect(_post_save, sender=model, dispatch_uid=f"audit_post_{model._meta.label}")
    post_delete.connect(_post_delete, sender=model, dispatch_uid=f"audit_del_{model._meta.label}")
    _registered.add(model)
    return model


audited = register


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.LOGIN,
        model_label="accounts.User",
        object_id=str(user.pk),
        object_repr=str(user),
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
    )


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user is not None:
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.LOGOUT,
            model_label="accounts.User",
            object_id=str(user.pk),
            object_repr=str(user),
        )


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    AuditEvent.objects.create(
        action=AuditEvent.Action.LOGIN_FAILED,
        model_label="accounts.User",
        object_repr=str(credentials.get("username", ""))[:255],
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
    )
