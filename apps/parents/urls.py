from django.urls import path

from . import views

app_name = "parents"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("start/", views.start_view, name="start"),
    path("logout/", views.logout_view, name="logout"),
    path("account/", views.account, name="account"),
    path("child/<int:student_id>/", views.child, name="child"),
    path("child/<int:student_id>/diary/<int:diary_id>.<str:kind>", views.diary, name="diary"),
    path("child/<int:student_id>/voucher/<int:voucher_id>.pdf", views.voucher, name="voucher"),
    path("child/<int:student_id>/result/<int:exam_id>.pdf", views.result, name="result"),
    path("codes/", views.codes, name="codes"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
    path("notices/", views.notices, name="notices"),
    path("notices/<int:notice_id>/", views.notice, name="notice"),
    path("notices/<int:notice_id>/file/", views.notice_file, name="notice_file"),
]
