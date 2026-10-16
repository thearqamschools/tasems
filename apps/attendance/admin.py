from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import SectionAttendance


@admin.register(SectionAttendance)
class SectionAttendanceAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("section", "date", "branch", "present", "absent", "leave", "late", "taken_by")
    list_filter = ("date", "branch")
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False
