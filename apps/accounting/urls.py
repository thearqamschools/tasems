from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.new, name="new"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/bill/", views.attachment, name="attachment"),
]
