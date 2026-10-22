from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.index, name="index"),
    path("barcode/", views.quick_receive, name="quick"),
    path("family/", views.family_vouchers, name="family_vouchers"),
    path("family/print/", views.family_vouchers_pdf, name="family_vouchers_pdf"),
    path("family/<int:family_id>/pdf/", views.family_voucher_pdf, name="family_voucher_pdf"),
    path("family/<int:family_id>/receive/", views.family_receive, name="family_receive"),
    path("generate/", views.generate, name="generate"),
    path("vouchers/", views.vouchers, name="vouchers"),
    path("vouchers/print/", views.vouchers_pdf, name="vouchers_pdf"),
    path("voucher/<int:voucher_id>/pdf/", views.voucher_pdf, name="voucher_pdf"),
    path("voucher/<int:voucher_id>/cancel/", views.cancel_voucher, name="cancel_voucher"),
    path("voucher/<int:voucher_id>/receive/", views.receive, name="receive"),
    path("voucher/<int:voucher_id>/edit/", views.edit_voucher, name="edit_voucher"),
    path("receipt/<int:payment_id>/", views.receipt, name="receipt"),
    path("receipt/<int:payment_id>/reverse/", views.reverse_payment, name="reverse_payment"),
    path("receipt/<int:payment_id>/attachment/", views.payment_attachment, name="payment_attachment"),
    path("student/<int:student_id>/", views.student, name="student"),
    path("student/<int:student_id>/voucher/", views.issue, name="issue"),
    path("student/<int:student_id>/discount/", views.concession_new, name="concession_new"),
    path("charge/<int:charge_id>/cancel/", views.cancel_charge, name="cancel_charge"),
    path("discounts/", views.concessions, name="concessions"),
    path("defaulters/", views.defaulters, name="defaulters"),
    path("collections/", views.collections, name="collections"),
    path("royalty/", views.royalty, name="royalty"),
    path("royalty/branch/<int:branch_id>/", views.royalty_branch, name="royalty_branch"),
    path("royalty/payment/<int:payment_id>/attachment/", views.royalty_attachment, name="royalty_attachment"),
    path("jazzcash/vouchers.xlsx", views.jazzcash_export, name="jazzcash_export"),
    path("payments/import/", views.payments_import, name="payments_import"),
]
