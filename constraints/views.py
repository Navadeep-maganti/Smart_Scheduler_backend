from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response

from .models import ConstraintType, FacultyConstraint
from .permissions import ConstraintTypePermission, FacultyConstraintPermission
from .serializers import ConstraintTypeSerializer, FacultyConstraintSerializer


class QueryFilterMixin:
    filter_map = {}
    search_fields = ()

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        for param, lookup in self.filter_map.items():
            value = params.get(param)
            if value not in (None, ""):
                queryset = queryset.filter(**{lookup: value})

        search = params.get("search")
        if search and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(query)

        ordering = params.get("ordering")
        if ordering:
            queryset = queryset.order_by(*[item.strip() for item in ordering.split(",") if item.strip()])

        return queryset


class SafeDestroyMixin:
    success_delete_message = "Record deleted successfully."

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            protected_names = sorted({obj.__class__.__name__ for obj in exc.protected_objects})
            raise serializers.ValidationError(
                {
                    "detail": "This record cannot be deleted because it is still referenced by other records.",
                    "protected_models": protected_names,
                }
            ) from exc

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": self.success_delete_message}, status=status.HTTP_200_OK)


class ConstraintTypeViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = ConstraintType.objects.all()
    serializer_class = ConstraintTypeSerializer
    permission_classes = [ConstraintTypePermission]
    success_delete_message = "Constraint type deleted successfully."
    filter_map = {
        "constraint_category": "constraint_category__iexact",
        "is_hard_constraint": "is_hard_constraint",
        "priority_level": "priority_level",
    }
    search_fields = ("constraint_name", "constraint_category", "description")


class FacultyConstraintViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = FacultyConstraint.objects.select_related(
        "faculty__user",
        "faculty__department",
        "day",
        "slot",
        "constraint_type",
    ).all()
    serializer_class = FacultyConstraintSerializer
    permission_classes = [FacultyConstraintPermission]
    success_delete_message = "Faculty constraint deleted successfully."
    filter_map = {
        "faculty_id": "faculty_id",
        "department_id": "faculty__department_id",
        "day_id": "day_id",
        "slot_id": "slot_id",
        "constraint_type_id": "constraint_type_id",
    }
    search_fields = (
        "faculty__faculty_name",
        "faculty__user__email",
        "day__day_name",
        "constraint_type__constraint_name",
        "remarks",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.has_permission_code("constraints:read"):
            return queryset

        if hasattr(user, "faculty_profile"):
            if user.has_permission_code("constraints:read_department"):
                return queryset.filter(faculty__department_id=user.faculty_profile.department_id)
            if user.has_permission_code("constraints:read_self"):
                return queryset.filter(faculty_id=user.faculty_profile.faculty_id)

        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        faculty = serializer.validated_data["faculty"]

        if user.has_permission_code("constraints:write"):
            serializer.save()
            return

        if not hasattr(user, "faculty_profile"):
            raise serializers.ValidationError({"faculty": "This user is not linked to a faculty profile."})

        if user.has_permission_code("constraints:write_department"):
            if faculty.department_id != user.faculty_profile.department_id:
                raise serializers.ValidationError(
                    {"faculty": "You can only manage constraints for faculty in your department."}
                )
            serializer.save()
            return

        if user.has_permission_code("constraints:write_self"):
            if faculty.faculty_id != user.faculty_profile.faculty_id:
                raise serializers.ValidationError(
                    {"faculty": "You can only manage your own faculty constraints."}
                )
            serializer.save()
            return

        raise serializers.ValidationError({"detail": "You do not have permission to create this constraint."})

    def perform_update(self, serializer):
        self.perform_create(serializer)
