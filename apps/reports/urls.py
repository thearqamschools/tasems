from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.index, name="index"),
    path("class-strength/", views.class_strength, name="class_strength"),
    path("new-admissions/", views.new_admissions, name="new_admissions"),
    path("attendance-month/", views.attendance_month, name="attendance_month"),
]
