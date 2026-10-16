from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, RoleAssignment, User


class RoleAssignmentInline(admin.TabularInline):
    model = RoleAssignment
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("role", "branch")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("TASEMS", {"fields": ("full_name_ur", "phone", "preferred_language")}),)
    list_display = ("username", "first_name", "last_name", "phone", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "phone", "email")
    inlines = [RoleAssignmentInline]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "requires_mfa", "is_system")
    search_fields = ("name", "code")
    filter_horizontal = ("permissions",)


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "scope", "head_office", "region", "branch", "is_active")
    list_filter = ("role", "scope", "is_active")
    autocomplete_fields = ("user", "role", "branch")
