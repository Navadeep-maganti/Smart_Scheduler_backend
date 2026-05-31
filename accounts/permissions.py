from rest_framework.permissions import BasePermission

from .models import AppUser


class IsActiveAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class RolePermission(BasePermission):
    allowed_roles = ()
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.has_role(*self.allowed_roles)
        )


class IsAdmin(RolePermission):
    allowed_roles = (AppUser.Role.ADMIN,)
    message = "Only admin users can perform this action."


class IsFaculty(RolePermission):
    allowed_roles = (AppUser.Role.FACULTY,)
    message = "Only faculty users can perform this action."


class IsStudent(RolePermission):
    allowed_roles = (AppUser.Role.STUDENT,)
    message = "Only student users can perform this action."


class IsHOD(RolePermission):
    allowed_roles = (AppUser.Role.HOD,)
    message = "Only HOD users can perform this action."


class IsFacultyOrHOD(RolePermission):
    allowed_roles = (AppUser.Role.FACULTY, AppUser.Role.HOD)
    message = "Only faculty or HOD users can perform this action."


class IsAdminOrHOD(RolePermission):
    allowed_roles = (AppUser.Role.ADMIN, AppUser.Role.HOD)
    message = "Only admin or HOD users can perform this action."


class HasPermissionCode(BasePermission):
    required_permission = None
    message = "You do not have the required role permission."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and self.required_permission
            and request.user.has_permission_code(self.required_permission)
        )


class CanManageRoles(HasPermissionCode):
    required_permission = "auth:manage_roles"
    message = "You do not have permission to manage user roles."


class CanReadUsers(HasPermissionCode):
    required_permission = "users:read"
    message = "You do not have permission to read users."


class CanWriteUsers(HasPermissionCode):
    required_permission = "users:write"
    message = "You do not have permission to manage users."
