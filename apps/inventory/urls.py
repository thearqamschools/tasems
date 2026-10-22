from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.index, name="index"),
    path("items/new/", views.item_form, name="item_new"),
    path("items/<int:pk>/", views.item, name="item"),
    path("items/<int:pk>/edit/", views.item_form, name="item_edit"),
    path("stock/", views.stock, name="stock"),
    path("sell/", views.sell, name="sell"),
    path("sales/", views.sales, name="sales"),
    path("sales/<int:pk>/", views.receipt, name="receipt"),
    path("sales/<int:pk>/cancel/", views.cancel, name="cancel"),
]
