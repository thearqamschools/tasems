from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import Exam, GradingScheme, Mark, Paper


class PaperInline(admin.TabularInline):
    model = Paper
    extra = 1


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "session", "branch", "starts_on", "marks_due_on", "is_published")
    list_filter = ("kind", "session", "is_published")
    inlines = [PaperInline]


@admin.register(GradingScheme)
class GradingSchemeAdmin(admin.ModelAdmin):
    list_display = ("name", "test_weight", "mid_weight", "final_weight", "pass_percent", "positions", "is_default")


@admin.register(Mark)
class MarkAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("student", "paper", "obtained", "status", "branch")
    list_filter = ("paper__exam", "status")

    def has_add_permission(self, request):
        return False
