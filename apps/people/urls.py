from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.student_list, name="student_list"),
    path("new/", views.student_create, name="student_create"),
    path("import/", views.student_import, name="student_import"),
    path("import/template.xlsx", views.import_template, name="import_template"),
    path("<int:pk>/", views.student_detail, name="student_detail"),
    path("<int:pk>/edit/", views.student_edit, name="student_edit"),
]
