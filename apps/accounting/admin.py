from django.contrib import admin

from .models import Expense, ExpenseHead


@admin.register(ExpenseHead)
class ExpenseHeadAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sort_order", "is_active"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["date", "branch", "head", "amount", "paid_from", "is_cancelled"]
    list_filter = ["branch", "head", "is_cancelled"]
