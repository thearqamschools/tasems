from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.today, name="today"),
    path("section/<int:section_id>/<str:date>/", views.take_register, name="take"),
    path("absent/", views.absentees, name="absentees"),
    path("branches/", views.branches_summary, name="branches"),
]
