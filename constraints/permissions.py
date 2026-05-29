from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import AppUser


class ConstraintTypePermission(BasePermission):
    message = "You do not have permission to access constraint types."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.has_permission_code("constraints:write")


class FacultyConstraintPermission(BasePermission):
    message = "You do not have permission to access faculty constraints."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if request.method in SAFE_METHODS:
            return user.has_permission_code("constraints:read") or user.has_permission_code("constraints:read_self") or user.has_permission_code("constraints:read_department")
        return (
            user.has_permission_code("constraints:write")
            or user.has_permission_code("constraints:write_self")
            or user.has_permission_code("constraints:write_department")
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.has_permission_code("constraints:write") or user.has_permission_code("constraints:read"):
            return True

        if hasattr(user, "faculty_profile"):
            if obj.faculty_id == user.faculty_profile.faculty_id:
                return True

            if user.role == AppUser.Role.HOD and obj.faculty.department_id == user.faculty_profile.department_id:
                return True

        return False
