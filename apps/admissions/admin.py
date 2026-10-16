from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(ScopedAdminMixin, admin.ModelAdmin):
    """For head office look-ups; inquiries are worked on the Admissions screens."""

    list_display = ("child_name", "class_level", "parent_name", "phone", "source", "status", "branch", "created_at")
    list_filter = ("status", "source", "branch")
    search_fields = ("child_name", "parent_name", "phone")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
