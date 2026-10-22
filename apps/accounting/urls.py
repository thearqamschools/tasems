from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.new, name="new"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/bill/", views.attachment, name="attachment"),
    path("income/", views.incomes, name="incomes"),
    path("income/new/", views.income_new, name="income_new"),
    path("income/<int:pk>/cancel/", views.income_cancel, name="income_cancel"),
    path("book/", views.cash_book, name="book"),
    path("profit-loss/", views.profit_loss, name="profit_loss"),
    path("branches/", views.branches_statement, name="branches"),
]
