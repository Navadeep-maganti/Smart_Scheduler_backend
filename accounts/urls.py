from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    FacultyViewSet,
    LoginView,
    LogoutView,
    MeView,
    MeConstraintsView,
    MeProfileView,
    MeTimetableView,
    RefreshView,
    RegisterView,
    RolePermissionsView,
    StudentViewSet,
    UpdateUserRoleView,
    UserViewSet,
)

router = DefaultRouter(trailing_slash="/?")
router.register("users", UserViewSet, basename="auth-user")
router.register("faculty", FacultyViewSet, basename="auth-faculty")
router.register("students", StudentViewSet, basename="auth-student")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("register", RegisterView.as_view(), name="auth-register-no-slash"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("login", LoginView.as_view(), name="auth-login-no-slash"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("refresh", RefreshView.as_view(), name="auth-refresh-no-slash"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me", MeView.as_view(), name="auth-me-no-slash"),
    path("me/profile/", MeProfileView.as_view(), name="auth-me-profile"),
    path("me/profile", MeProfileView.as_view(), name="auth-me-profile-no-slash"),
    path("me/timetable/", MeTimetableView.as_view(), name="auth-me-timetable"),
    path("me/timetable", MeTimetableView.as_view(), name="auth-me-timetable-no-slash"),
    path("me/constraints/", MeConstraintsView.as_view(), name="auth-me-constraints"),
    path("me/constraints", MeConstraintsView.as_view(), name="auth-me-constraints-no-slash"),
    path("permissions/", RolePermissionsView.as_view(), name="auth-permissions"),
    path("permissions", RolePermissionsView.as_view(), name="auth-permissions-no-slash"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("change-password", ChangePasswordView.as_view(), name="auth-change-password-no-slash"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("logout", LogoutView.as_view(), name="auth-logout-no-slash"),
    path("users/<int:user_id>/role/", UpdateUserRoleView.as_view(), name="auth-update-user-role"),
    path("users/<int:user_id>/role", UpdateUserRoleView.as_view(), name="auth-update-user-role-no-slash"),
]

urlpatterns += router.urls
