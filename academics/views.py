from django.db.models.deletion import ProtectedError
from django.db.models import Q
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.response import Response

from .models import AcademicTerm, Department, Section, Subject
from .permissions import AcademicsPermission
from .serializers import (
    AcademicTermSerializer,
    DepartmentSerializer,
    SectionSerializer,
    SubjectSerializer,
)


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


class DepartmentViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Department.objects.select_related("hod__user", "hod__department").all()
    serializer_class = DepartmentSerializer
    permission_classes = [AcademicsPermission]
    success_delete_message = "Department deleted successfully."
    filter_map = {
        "department_code": "department_code__iexact",
        "hod_id": "hod_id",
    }
    search_fields = ("department_code", "department_name")

    def get_permissions(self):
        if self.action == "list":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_authenticators(self):
        if self.action == "list":
            return []
        return super().get_authenticators()


class AcademicTermViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = AcademicTerm.objects.all()
    serializer_class = AcademicTermSerializer
    permission_classes = [AcademicsPermission]
    success_delete_message = "Academic term deleted successfully."
    filter_map = {
        "term_type": "term_type",
        "academic_year": "academic_year",
        "is_active": "is_active",
    }
    search_fields = ("academic_year",)


class SectionViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Section.objects.select_related("department", "academic_term").all()
    serializer_class = SectionSerializer
    permission_classes = [AcademicsPermission]
    success_delete_message = "Section deleted successfully."
    filter_map = {
        "department_id": "department_id",
        "academic_term_id": "academic_term_id",
        "year_number": "year_number",
        "section_name": "section_name__iexact",
    }
    search_fields = ("section_name", "department__department_code", "department__department_name")

    def get_permissions(self):
        if self.action == "list":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_authenticators(self):
        if self.action == "list":
            return []
        return super().get_authenticators()


class SubjectViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.select_related("department").all()
    serializer_class = SubjectSerializer
    permission_classes = [AcademicsPermission]
    success_delete_message = "Subject deleted successfully."
    filter_map = {
        "department_id": "department_id",
        "subject_type": "subject_type",
        "required_room_type": "required_room_type",
    }
    search_fields = ("subject_code", "subject_title", "department__department_code", "department__department_name")
