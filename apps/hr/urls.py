from django.urls import path

from . import views

app_name = "hr"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.employee_form, name="employee_new"),
    path("<int:employee_id>/", views.employee, name="employee"),
    path("<int:employee_id>/edit/", views.employee_form, name="employee_edit"),
    path("<int:employee_id>/leave/", views.leave_new, name="leave_new"),
    path("import/", views.staff_import, name="staff_import"),
    path("attendance/import/", views.punches_import, name="punches_import"),
    path("attendance/", views.day, name="day"),
    path("attendance/month/", views.month, name="month"),
    path("leave/", views.leaves, name="leaves"),
    path("me/", views.mine, name="mine"),
    path("me/leave/", views.my_leave, name="my_leave"),
    path("me/leave/<int:leave_id>/withdraw/", views.my_leave_cancel, name="my_leave_cancel"),
]
