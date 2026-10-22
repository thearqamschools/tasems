from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.index, name="index"),
    path("finalise/", views.finalise, name="finalise"),
    path("salaries/", views.salaries, name="salaries"),
    path("<int:run_id>/cancel/", views.cancel, name="cancel"),
    path("<int:run_id>/payslips.pdf", views.payslips_pdf, name="payslips"),
]
