from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import ClassLevel, CurriculumSubject, Section, Subject


class CurriculumInline(admin.TabularInline):
    model = CurriculumSubject
    extra = 0


@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "name_ur", "stage", "sort_order", "is_active")
    list_filter = ("stage",)
    inlines = [CurriculumInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "name_ur", "code", "is_rtl", "is_active")
    search_fields = ("name", "code")


@admin.register(Section)
class SectionAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "branch", "session", "class_teacher", "capacity", "is_active")
    list_filter = ("session", "class_level", "branch")
    autocomplete_fields = ("class_teacher",)
