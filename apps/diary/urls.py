from django.urls import path

from . import views

app_name = "diary"

urlpatterns = [
    path("", views.day, name="day"),
    path("section/<int:section_id>/<str:date>/", views.write, name="write"),
    path("<int:pk>/", views.view, name="view"),
    path("<int:pk>/diary.pdf", views.pdf, name="pdf"),
    path("<int:pk>/diary.png", views.image, name="image"),
]
