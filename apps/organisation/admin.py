from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import AcademicSession, Branch, Campus, HeadOffice, Region


@admin.register(HeadOffice)
class HeadOfficeAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "phone", "is_active")
    search_fields = ("name", "city")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "head_office", "is_active")
    list_filter = ("head_office", "is_active")
    search_fields = ("name",)


@admin.register(Branch)
class BranchAdmin(ScopedAdminMixin, admin.ModelAdmin):
    branch_field = "id"
    list_display = ("name", "code", "head_office", "region", "ownership", "royalty_percent", "city", "is_active")
    list_filter = ("head_office", "region", "ownership", "is_active")
    search_fields = ("name", "code", "city")


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ("name", "starts_on", "ends_on", "is_current")


@admin.register(Campus)
class CampusAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "branch", "gender_group", "is_active")
    list_filter = ("gender_group", "branch")
