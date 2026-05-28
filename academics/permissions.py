from rest_framework.permissions import BasePermission, SAFE_METHODS


class AcademicsPermission(BasePermission):
    message = "You do not have permission to access this academic resource."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False

        if request.method in SAFE_METHODS:
            return True

        return user.has_permission_code("department:write")
