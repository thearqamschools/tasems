from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("timetable/", views.index, name="index"),
    path("holidays/", views.holidays, name="holidays"),
    path("timetable/bell-times/", views.periods, name="periods"),
    path("timetable/mine/", views.my_timetable, name="my_timetable"),
    path("timetable/teacher/<int:user_id>/", views.teacher_timetable, name="teacher_timetable"),
    path("section/<int:section_id>/subjects/", views.section_subjects, name="section_subjects"),
    path("section/<int:section_id>/timetable/", views.section_timetable, name="section_timetable"),
]
