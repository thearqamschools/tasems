from django.contrib import admin

from apps.core.admin_mixins import ScopedAdminMixin

from .models import BranchFeeSettings, Charge, FeeHead, FeeRate, Payment, PaymentChannel, Voucher, VoucherCounter


@admin.register(FeeHead)
class FeeHeadAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "kind", "charge_months", "counts_for_royalty", "sort_order", "is_active")
    list_editable = ("sort_order",)


@admin.register(FeeRate)
class FeeRateAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ("branch", "head", "class_level", "amount", "sibling_amount", "effective_from")
    list_filter = ("head", "branch")


@admin.register(BranchFeeSettings)
class BranchFeeSettingsAdmin(ScopedAdminMixin, admin.ModelAdmin):
    scope_permission_action = "change"
    list_display = ("branch", "due_day", "late_fine", "bank_name", "account_number")
    fieldsets = (
        (None, {"fields": ("branch", "due_day", "late_fine", "allow_partial_payment")}),
        (
            "Bank details printed on vouchers",
            {"fields": ("bank_name", "bank_branch", "account_title", "account_number")},
        ),
        (
            "Voucher text",
            {
                "fields": (
                    "receipt_whatsapp",
                    "voucher_note",
                    "print_back_side",
                    "back_title",
                    "back_notes_ur",
                    "back_notes_en",
                    "back_footer_ur",
                )
            },
        ),
    )


@admin.register(PaymentChannel)
class PaymentChannelAdmin(admin.ModelAdmin):
    list_display = ("title", "method", "branch", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")


@admin.register(VoucherCounter)
class VoucherCounterAdmin(admin.ModelAdmin):
    list_display = ("next_number",)

    def has_add_permission(self, request):
        return not VoucherCounter.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnly(ScopedAdminMixin, admin.ModelAdmin):
    """Money records change only through the fee screens, where every change is checked and audited."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Voucher)
class VoucherAdmin(ReadOnly):
    list_display = ("number", "student", "first_month", "last_month", "payable", "status", "branch")
    list_filter = ("status", "first_month")
    search_fields = ("=number", "student__admission_no")


@admin.register(Charge)
class ChargeAdmin(ReadOnly):
    list_display = ("student", "head", "month", "amount", "source", "is_cancelled", "branch")
    list_filter = ("head", "source", "is_cancelled")


@admin.register(Payment)
class PaymentAdmin(ReadOnly):
    list_display = ("receipt_no", "student", "amount", "paid_on", "method", "is_reversed", "branch")
    list_filter = ("method", "is_reversed")
