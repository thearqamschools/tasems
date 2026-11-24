from django.urls import path

from . import views, views_year

app_name = "exams"

urlpatterns = [
    path("", views.index, name="index"),
    path("add-session-exams/", views_year.add_session_exams, name="add_session_exams"),
    path("<int:exam_id>/papers/", views_year.papers, name="papers"),
    path("<int:exam_id>/date-sheet.pdf", views_year.date_sheet_pdf, name="date_sheet_pdf"),
    path("<int:exam_id>/section/<int:section_id>/marks/", views_year.section_marks, name="section_marks"),
    path("<int:exam_id>/section/<int:section_id>/result-cards.pdf", views_year.cards, name="exam_cards"),
    path("question-paper/<int:paper_id>/", views_year.question_paper, name="question_paper"),
    path("<int:exam_id>/results/", views_year.report, name="report"),
    path("progress/<int:student_id>/", views_year.progress_report, name="progress"),
    path("marks-reader-skill.zip", views_year.marks_skill, name="marks_skill"),
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
