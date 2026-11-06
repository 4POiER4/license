from django.contrib.auth import views as auth_views
from django.urls import path
from registry import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("login/", views.DepartmentLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/password/", auth_views.PasswordChangeView.as_view(template_name="registration/password_change.html", success_url="/account/password/done/", extra_context={"title": "Смена пароля"}), name="password_change"),
    path("account/password/done/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_done.html", extra_context={"title": "Пароль изменён"}), name="password_change_done"),
    path("", views.dashboard, name="dashboard"),
    path("contracts/", views.contracts, name="contracts"),
    path("contracts/new/", views.contract_create, name="contract_create"),
    path("contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:pk>/edit/", views.contract_edit, name="contract_edit"),
    path("licenses/new/", views.license_create, name="license_create"),
    path("licenses/<int:pk>/", views.license_detail, name="license_detail"),
    path("licenses/<int:pk>/edit/", views.license_edit, name="license_edit"),
    path("notifications/", views.notifications, name="notifications"),
    path("renewals/", views.renewals, name="renewals"),
    path("export/", views.export_csv, name="export_csv"),
]
