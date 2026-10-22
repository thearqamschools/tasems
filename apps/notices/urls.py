from django.urls import path

from . import views

app_name = "notices"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.new, name="new"),
    path("<int:notice_id>/", views.detail, name="detail"),
    path("<int:notice_id>/withdraw/", views.withdraw, name="withdraw"),
    path("<int:notice_id>/file/", views.attachment, name="attachment"),
    path("messages/", views.compose, name="compose"),
    path("messages/templates/", views.templates, name="templates"),
    path("messages/templates/new/", views.template_form, name="template_new"),
    path("messages/templates/<int:template_id>/", views.template_form, name="template_edit"),
]
