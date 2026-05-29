from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduler.engine import SchedulerEngine
from .models import SessionGroup, SessionGroupMember, TeachingAssignment, Timetable, TimetableEntry
from .permissions import TimetablePermission
from .serializers import (
    SchedulerRegenerateSerializer,
    SchedulerRequestSerializer,
    SchedulerResultSerializer,
    SessionGroupMemberSerializer,
    SessionGroupSerializer,
    TeachingAssignmentSerializer,
    TimetableEntrySerializer,
    TimetableSerializer,
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


class TimetableScopedViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    permission_classes = [TimetablePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.has_permission_code("timetable:read") or user.has_permission_code("timetable:write"):
            return queryset

        if hasattr(user, "faculty_profile"):
            department_id = user.faculty_profile.department_id
            faculty_id = user.faculty_profile.faculty_id

            if user.has_permission_code("timetable:read_department") or user.has_permission_code("timetable:write_department") or user.has_permission_code("timetable:review_department"):
                return self.filter_department_queryset(queryset, department_id)

            if user.has_permission_code("timetable:read_assigned"):
                return self.filter_faculty_queryset(queryset, faculty_id)

        return queryset

    def filter_department_queryset(self, queryset, department_id):
        return queryset

    def filter_faculty_queryset(self, queryset, faculty_id):
        return queryset.none()


class TeachingAssignmentViewSet(TimetableScopedViewSet):
    queryset = TeachingAssignment.objects.select_related("section__department", "subject", "faculty__user", "preferred_room").all()
    serializer_class = TeachingAssignmentSerializer
    success_delete_message = "Teaching assignment deleted successfully."
    filter_map = {
        "section_id": "section_id",
        "faculty_id": "faculty_id",
        "subject_code": "subject_id",
        "required_room_type": "required_room_type",
        "department_id": "section__department_id",
    }
    search_fields = ("subject__subject_code", "subject__subject_title", "faculty__faculty_name", "section__section_name")

    def filter_department_queryset(self, queryset, department_id):
        return queryset.filter(section__department_id=department_id)

    def filter_faculty_queryset(self, queryset, faculty_id):
        return queryset.filter(faculty_id=faculty_id)


class SessionGroupViewSet(TimetableScopedViewSet):
    queryset = SessionGroup.objects.select_related("preferred_building").prefetch_related("members__assignment__section").all()
    serializer_class = SessionGroupSerializer
    success_delete_message = "Session group deleted successfully."
    filter_map = {
        "group_category": "group_category",
        "same_time_required": "same_time_required",
        "same_building_required": "same_building_required",
        "preferred_building_id": "preferred_building_id",
    }
    search_fields = ("group_name",)

    def filter_department_queryset(self, queryset, department_id):
        return queryset.filter(members__assignment__section__department_id=department_id).distinct()

    def filter_faculty_queryset(self, queryset, faculty_id):
        return queryset.filter(members__assignment__faculty_id=faculty_id).distinct()


class SessionGroupMemberViewSet(TimetableScopedViewSet):
    queryset = SessionGroupMember.objects.select_related("group", "assignment__subject", "assignment__section", "assignment__faculty").all()
    serializer_class = SessionGroupMemberSerializer
    success_delete_message = "Session group member deleted successfully."
    filter_map = {
        "group_id": "group_id",
        "assignment_id": "assignment_id",
        "faculty_id": "assignment__faculty_id",
        "department_id": "assignment__section__department_id",
    }

    def filter_department_queryset(self, queryset, department_id):
        return queryset.filter(assignment__section__department_id=department_id)

    def filter_faculty_queryset(self, queryset, faculty_id):
        return queryset.filter(assignment__faculty_id=faculty_id)


class TimetableViewSet(TimetableScopedViewSet):
    queryset = Timetable.objects.select_related("section__department", "term", "generated_by").all()
    serializer_class = TimetableSerializer
    success_delete_message = "Timetable deleted successfully."
    filter_map = {
        "section_id": "section_id",
        "term_id": "term_id",
        "status": "status",
        "department_id": "section__department_id",
    }
    search_fields = ("section__section_name", "section__department__department_code", "term__academic_year")

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)

    def filter_department_queryset(self, queryset, department_id):
        return queryset.filter(section__department_id=department_id)

    def filter_faculty_queryset(self, queryset, faculty_id):
        return queryset.filter(entries__assignment__faculty_id=faculty_id).distinct()

    @action(detail=False, methods=["get"], url_path="by-section")
    def by_section(self, request):
        section_id = request.query_params.get("section_id")
        term_id = request.query_params.get("term_id")
        if not section_id or not term_id:
            raise serializers.ValidationError({"detail": "section_id and term_id are required."})
        queryset = self.filter_queryset(self.get_queryset()).filter(section_id=section_id, term_id=term_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        timetable = self.get_object()
        timetable.status = Timetable.Status.PUBLISHED
        timetable.published_at = timetable.published_at or timezone.now()
        timetable.save(update_fields=["status", "published_at"])
        return Response({"message": "Timetable published successfully.", "timetable": self.get_serializer(timetable).data})

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        timetable = self.get_object()
        timetable.status = Timetable.Status.ARCHIVED
        timetable.save(update_fields=["status"])
        return Response({"message": "Timetable archived successfully.", "timetable": self.get_serializer(timetable).data})


class TimetableEntryViewSet(TimetableScopedViewSet):
    queryset = TimetableEntry.objects.select_related(
        "timetable__section__department",
        "assignment__subject",
        "assignment__faculty",
        "day",
        "starting_slot",
        "room",
    ).all()
    serializer_class = TimetableEntrySerializer
    success_delete_message = "Timetable entry deleted successfully."
    filter_map = {
        "timetable_id": "timetable_id",
        "day_id": "day_id",
        "room_id": "room_id",
        "faculty_id": "assignment__faculty_id",
        "section_id": "timetable__section_id",
        "status": "status",
        "department_id": "timetable__section__department_id",
    }
    search_fields = ("assignment__subject__subject_code", "assignment__subject__subject_title", "room__room_name", "assignment__faculty__faculty_name")

    def filter_department_queryset(self, queryset, department_id):
        return queryset.filter(timetable__section__department_id=department_id)

    def filter_faculty_queryset(self, queryset, faculty_id):
        return queryset.filter(assignment__faculty_id=faculty_id)


class SchedulerBaseView(APIView):
    permission_classes = [TimetablePermission]
    serializer_class = SchedulerRequestSerializer
    persist = False

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        result = SchedulerEngine().generate(
            term_id=validated["term"].term_id,
            section_ids=[section.section_id for section in validated.get("sections", [])] or None,
            generated_by_id=request.user.user_id,
            locked_timetable_ids=[tt.timetable_id for tt in validated.get("locked_timetables", [])] or None,
            persist=self.persist,
        )

        payload = self.serialize_result(result, validated["term"].term_id, validated.get("sections", []))
        status_code = status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
        return Response(payload, status=status_code)

    def serialize_result(self, result, term_id, sections):
        created_timetable_ids = []
        if self.persist and result.success:
            section_ids = [section.section_id for section in sections] if sections else sorted(
                {allocation.session.section_id for allocation in result.allocations}
            )
            created_timetable_ids = list(
                Timetable.objects.filter(term_id=term_id, section_id__in=section_ids)
                .order_by("-timetable_id")
                .values_list("timetable_id", flat=True)[: len(section_ids)]
            )
            created_timetable_ids.reverse()

        payload = {
            "success": result.success,
            "message": result.message,
            "allocation_count": len(result.allocations),
            "unscheduled_count": len(result.unscheduled_units),
            "allocations": [
                {
                    "assignment_id": allocation.session.assignment_id,
                    "section_id": allocation.session.section_id,
                    "faculty_id": allocation.session.faculty_id,
                    "subject_code": allocation.session.subject_code,
                    "day_id": allocation.day_id,
                    "starting_slot_id": allocation.starting_slot_id,
                    "slot_ids": list(allocation.slot_ids),
                    "room_id": allocation.room_id,
                }
                for allocation in result.allocations
            ],
            "unscheduled_units": [unit.unit_id for unit in result.unscheduled_units],
        }
        if created_timetable_ids:
            payload["created_timetable_ids"] = created_timetable_ids
        return SchedulerResultSerializer(payload).data


class GeneratePreviewView(SchedulerBaseView):
    serializer_class = SchedulerRequestSerializer
    persist = False


class GenerateTimetableView(SchedulerBaseView):
    serializer_class = SchedulerRequestSerializer
    persist = True


class RegenerateTimetableView(SchedulerBaseView):
    serializer_class = SchedulerRegenerateSerializer
    persist = True

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        archive_timetables = validated.get("archive_timetables", [])
        if archive_timetables:
            Timetable.objects.filter(
                timetable_id__in=[timetable.timetable_id for timetable in archive_timetables]
            ).update(status=Timetable.Status.ARCHIVED)

        result = SchedulerEngine().generate(
            term_id=validated["term"].term_id,
            section_ids=[section.section_id for section in validated.get("sections", [])] or None,
            generated_by_id=request.user.user_id,
            locked_timetable_ids=[tt.timetable_id for tt in validated.get("locked_timetables", [])] or None,
            persist=True,
        )

        payload = self.serialize_result(result, validated["term"].term_id, validated.get("sections", []))
        if archive_timetables:
            payload["archived_timetable_ids"] = [timetable.timetable_id for timetable in archive_timetables]
        status_code = status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
        return Response(payload, status=status_code)
