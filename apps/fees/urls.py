from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.index, name="index"),
    path("generate/", views.generate, name="generate"),
    path("vouchers/", views.vouchers, name="vouchers"),
    path("vouchers/print/", views.vouchers_pdf, name="vouchers_pdf"),
    path("voucher/<int:voucher_id>/pdf/", views.voucher_pdf, name="voucher_pdf"),
    path("voucher/<int:voucher_id>/cancel/", views.cancel_voucher, name="cancel_voucher"),
    path("voucher/<int:voucher_id>/receive/", views.receive, name="receive"),
    path("receipt/<int:payment_id>/", views.receipt, name="receipt"),
    path("receipt/<int:payment_id>/reverse/", views.reverse_payment, name="reverse_payment"),
    path("student/<int:student_id>/", views.student, name="student"),
    path("student/<int:student_id>/voucher/", views.issue, name="issue"),
    path("student/<int:student_id>/discount/", views.concession_new, name="concession_new"),
    path("charge/<int:charge_id>/cancel/", views.cancel_charge, name="cancel_charge"),
    path("discounts/", views.concessions, name="concessions"),
    path("defaulters/", views.defaulters, name="defaulters"),
    path("collections/", views.collections, name="collections"),
    path("royalty/", views.royalty, name="royalty"),
]
