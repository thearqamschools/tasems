from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import Enrolment, Guardian, Student, StudentGuardian


class GuardianLinkInline(admin.TabularInline):
    model = StudentGuardian
    extra = 0
    autocomplete_fields = ("guardian",)


class EnrolmentInline(admin.TabularInline):
    model = Enrolment
    extra = 0


@admin.register(Student)
class StudentAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("admission_no", "full_name", "gender", "branch", "is_hifz", "status")
    list_filter = ("status", "gender", "is_hifz", "branch")
    search_fields = ("admission_no", "first_name", "last_name", "full_name_ur")
    inlines = [GuardianLinkInline, EnrolmentInline]


@admin.register(Guardian)
class GuardianAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("full_name", "phone", "branch")
    search_fields = ("full_name", "phone", "cnic")
    list_filter = ("branch",)
