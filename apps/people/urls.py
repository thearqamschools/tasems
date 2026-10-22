from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.student_list, name="student_list"),
    path("new/", views.student_create, name="student_create"),
    path("import/", views.student_import, name="student_import"),
    path("promotion/", views.promotion, name="promotion"),
    path("id-cards.pdf", views.id_cards, name="id_cards"),
    path("promotion/<int:section_id>/", views.promotion_section, name="promotion_section"),
    path("import/template.xlsx", views.import_template, name="import_template"),
    path("<int:pk>/", views.student_detail, name="student_detail"),
    path("<int:pk>/edit/", views.student_edit, name="student_edit"),
    path("<int:pk>/photo/", views.student_photo, name="student_photo"),
    path("<int:pk>/leave/", views.student_leave, name="student_leave"),
    path("<int:pk>/certificates/new/", views.certificate_new, name="certificate_new"),
    path("<int:pk>/certificates/<int:cert_id>.pdf", views.certificate_pdf, name="certificate_pdf"),
]
