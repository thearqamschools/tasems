from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import Diary, DiaryLayout, DiaryWeek


@admin.register(DiaryLayout)
class DiaryLayoutAdmin(admin.ModelAdmin):
    list_display = ("title", "header_colour")


@admin.register(DiaryWeek)
class DiaryWeekAdmin(admin.ModelAdmin):
    list_display = ("starts_on", "week_number", "theme", "branch")
    list_filter = ("branch",)


@admin.register(Diary)
class DiaryAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("section", "date", "status", "written_by", "branch")
    list_filter = ("status", "date", "branch")
    date_hierarchy = "date"
