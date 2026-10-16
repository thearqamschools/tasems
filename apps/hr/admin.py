from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import Employee, Holiday, HRSettings, LeaveType


@admin.register(HRSettings)
class HRSettingsAdmin(ScopedAdminMixin, admin.ModelAdmin):
    scope_permission_action = "change"
    list_display = ("branch", "duty_starts", "duty_ends", "grace_minutes", "half_day_after", "working_days")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "branch")
    list_filter = ("branch",)
    date_hierarchy = "date"


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "days_per_year", "is_paid", "is_active")


@admin.register(Employee)
class EmployeeAdmin(ScopedAdminMixin, admin.ModelAdmin):
    """Staff records are kept on the Staff screens; this list is for head office look-ups."""

    list_display = ("code", "full_name", "designation", "staff_type", "status", "branch")
    list_filter = ("staff_type", "status", "branch")
    search_fields = ("full_name", "code", "cnic", "phone")
    raw_id_fields = ("user",)
