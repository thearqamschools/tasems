from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.index, name="index"),
    path("finalise/", views.finalise, name="finalise"),
    path("salaries/", views.salaries, name="salaries"),
    path("manual/", views.manual, name="manual"),
    path("rules/", views.rules, name="rules"),
    path("advances/", views.advances, name="advances"),
    path("advances/<int:advance_id>/application/", views.advance_application, name="advance_application"),
    path("staff/<int:employee_id>/settlement/", views.settlement, name="settlement"),
    path("staff/<int:employee_id>/", views.person, name="person"),
    path("acknowledgement.pdf", views.acknowledgement, name="acknowledgement"),
    path("<int:run_id>/cancel/", views.cancel, name="cancel"),
    path("<int:run_id>/payslips.pdf", views.payslips_pdf, name="payslips"),
]
