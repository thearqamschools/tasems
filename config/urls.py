from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from apps.accounts.views import admin_login_redirect
from apps.core import views as core_views

admin.site.site_header = _("TASEMS setup")
admin.site.site_title = _("TASEMS setup")
admin.site.login = admin_login_redirect  # one sign-in (with two-step check) for the whole system

urlpatterns = [
    path("", core_views.home, name="home"),
    path("healthz", core_views.health, name="health"),
    path("branch/switch/", core_views.switch_branch, name="switch_branch"),
    path("accounts/", include("apps.accounts.urls")),
    path("students/", include("apps.people.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("diary/", include("apps.diary.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
