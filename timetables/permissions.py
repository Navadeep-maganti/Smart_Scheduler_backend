from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import AppUser


class TimetablePermission(BasePermission):
    message = "You do not have permission to access timetable resources."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if request.method in SAFE_METHODS:
            return True
        return (
            user.has_permission_code("timetable:write")
            or user.has_permission_code("timetable:write_department")
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method not in SAFE_METHODS:
            if user.has_permission_code("timetable:write"):
                return True
            return self._is_same_department(user, obj)

        if user.has_permission_code("timetable:read"):
            return True
        if user.has_permission_code("timetable:read_department") or user.has_permission_code("timetable:review_department"):
            return self._is_same_department(user, obj)
        if user.has_permission_code("timetable:read_assigned"):
            return self._is_assigned_to_faculty(user, obj)
        return True

    def _department_id_from_obj(self, obj):
        if hasattr(obj, "section") and obj.section_id:
            return obj.section.department_id
        if hasattr(obj, "assignment") and obj.assignment_id:
            return obj.assignment.section.department_id
        if hasattr(obj, "faculty") and obj.faculty_id:
            return obj.faculty.department_id
        if hasattr(obj, "group") and hasattr(obj, "assignment") and obj.assignment_id:
            return obj.assignment.section.department_id
        if hasattr(obj, "members"):
            member = obj.members.select_related("assignment__section").first()
            if member:
                return member.assignment.section.department_id
        return None

    def _is_same_department(self, user, obj):
        if not hasattr(user, "faculty_profile"):
            return False
        return self._department_id_from_obj(obj) == user.faculty_profile.department_id

    def _is_assigned_to_faculty(self, user, obj):
        if not hasattr(user, "faculty_profile"):
            return False
        faculty_id = user.faculty_profile.faculty_id
        if hasattr(obj, "faculty_id"):
            return obj.faculty_id == faculty_id
        if hasattr(obj, "assignment") and obj.assignment_id:
            return obj.assignment.faculty_id == faculty_id
        if hasattr(obj, "members"):
            return obj.members.filter(assignment__faculty_id=faculty_id).exists()
        return False
