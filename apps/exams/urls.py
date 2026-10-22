from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:exam_id>/section/<int:section_id>/", views.section_exam, name="section_exam"),
    path("<int:exam_id>/section/<int:section_id>/remarks/", views.remarks, name="remarks"),
    path("<int:exam_id>/date-sheet/", views.date_sheet, name="date_sheet"),
    path("<int:exam_id>/section/<int:section_id>/slips/", views.exam_slips, name="slips"),
    path("paper/<int:paper_id>/section/<int:section_id>/award-list/", views.award_list, name="award_list"),
    path("paper/<int:paper_id>/section/<int:section_id>/", views.enter_marks, name="enter_marks"),
    path("section/<int:section_id>/results/", views.section_results, name="section_results"),
    path("section/<int:section_id>/ratings/", views.ratings, name="ratings"),
    path("section/<int:section_id>/cards/", views.result_card, name="cards"),
    path("section/<int:section_id>/cards/<int:student_id>/", views.result_card, name="card"),
]
