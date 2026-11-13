from django.urls import path

from . import views

app_name = "hiring"

urlpatterns = [
    path("", views.index, name="index"),
    path("add/", views.add, name="add"),
    path("import/", views.import_cvs, name="import"),
    path("import/template.xlsx", views.import_template, name="import_template"),
    path("import/claude-skill.zip", views.import_skill, name="import_skill"),
    path("<int:pk>/", views.candidate, name="candidate"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("file/<int:file_id>/", views.cv_file, name="file"),
    path("vacancies/", views.vacancies, name="vacancies"),
    path("vacancies/<int:pk>/", views.vacancy, name="vacancy"),
    path("sheet/<int:application_id>/", views.sheet, name="sheet"),
    path("application/<int:application_id>/", views.application, name="application"),
    path("interviews/", views.interviews, name="interviews"),
    path("report/", views.report, name="report"),
    path("bin/", views.bin_view, name="bin"),
    path("posts/", views.posts, name="posts"),
]
