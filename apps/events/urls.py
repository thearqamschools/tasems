from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.event_form, name="new"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.event_form, name="edit"),
    path("<int:pk>/sell/", views.sell, name="sell"),
    path("<int:pk>/receipts/<int:sale_id>/", views.receipt, name="receipt"),
    path("<int:pk>/receipts/<int:sale_id>/refund/", views.refund, name="refund"),
    path("<int:pk>/classes/<int:level_id>/", views.class_list, name="class_list"),
    path("<int:pk>/expenses/new/", views.expense_new, name="expense_new"),
    path("<int:pk>/expenses/<int:expense_id>/cancel/", views.expense_cancel, name="expense_cancel"),
]
