from django.urls import path

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RegisterView,
    RolePermissionsView,
    UpdateUserRoleView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("permissions/", RolePermissionsView.as_view(), name="auth-permissions"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("users/<int:user_id>/role/", UpdateUserRoleView.as_view(), name="auth-update-user-role"),
]
