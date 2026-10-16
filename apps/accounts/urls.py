from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("verify/", views.verify_view, name="verify"),
    path("two-factor/setup/", views.mfa_setup_view, name="mfa_setup"),
    path("logout/", views.logout_view, name="logout"),
]
