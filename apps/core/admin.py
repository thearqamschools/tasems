from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only view of the audit trail."""

    list_display = ("occurred_at", "action", "model_label", "object_repr", "actor", "ip_address")
    list_filter = ("action", "model_label")
    search_fields = ("object_repr", "object_id")
    date_hierarchy = "occurred_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
