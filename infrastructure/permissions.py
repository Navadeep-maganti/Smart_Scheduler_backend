from rest_framework.permissions import SAFE_METHODS, BasePermission


class InfrastructurePermission(BasePermission):
    message = "You do not have permission to access infrastructure resources."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.has_permission_code("infrastructure:write")
