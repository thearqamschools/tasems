from django.urls import path

from . import views

app_name = "setup"

urlpatterns = [
    path("", views.hub, name="hub"),
    path("printer/", views.printer, name="printer"),
    path("sections/", views.sections, name="sections"),
    path("sections/new/", views.section_form, name="section_new"),
    path("sections/<int:pk>/", views.section_form, name="section_edit"),
    path("campuses/new/", views.campus_form, name="campus_new"),
    path("campuses/<int:pk>/", views.campus_form, name="campus_edit"),
    path("fees/", views.fees, name="fees"),
    path("fees/rates/new/", views.rate_form, name="rate_new"),
    path("fees/rates/<int:pk>/", views.rate_form, name="rate_edit"),
    path("fees/settings/", views.fee_settings, name="fee_settings"),
    path("fees/banks/new/", views.bank_form, name="bank_new"),
    path("fees/banks/<int:pk>/", views.bank_form, name="bank_edit"),
    path("fees/discounts/new/", views.discount_form, name="discount_new"),
    path("fees/discounts/<int:pk>/", views.discount_form, name="discount_edit"),
    path("branches/", views.branches, name="branches"),
    path("branches/new/", views.branch_form, name="branch_new"),
    path("branches/<int:pk>/", views.branch_form, name="branch_edit"),
    path("regions/new/", views.region_form, name="region_new"),
    path("regions/<int:pk>/", views.region_form, name="region_edit"),
    path("sessions/", views.sessions, name="sessions"),
    path("sessions/new/", views.session_form, name="session_new"),
    path("sessions/<int:pk>/", views.session_form, name="session_edit"),
    path("sessions/<int:pk>/current/", views.make_current, name="make_current"),
    path("users/", views.users, name="users"),
    path("users/new/", views.user_new, name="user_new"),
    path("users/<int:pk>/", views.user_detail, name="user"),
    path("users/<int:pk>/roles/<int:assignment_id>/end/", views.end_assignment, name="end_assignment"),
    path("users/<int:pk>/password/", views.reset_password, name="reset_password"),
    path("users/<int:pk>/active/", views.set_active, name="set_active"),
]
