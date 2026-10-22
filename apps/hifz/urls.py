from django.urls import path

from . import views

app_name = "hifz"

urlpatterns = [
    path("", views.index, name="index"),
    path("section/<int:section_id>/<str:date>/", views.record, name="record"),
    path("student/<int:student_id>/", views.student, name="student"),
    path("student/<int:student_id>/tests/<int:test_id>/cancel/", views.cancel_test, name="cancel_test"),
    path("report/", views.report, name="report"),
]
