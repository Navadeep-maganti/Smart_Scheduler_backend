import csv
from io import StringIO

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduler.engine import SchedulerEngine
from infrastructure.models import Timeslot
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


def expanded_slot_ids(entry, slot_id_by_number, slot_number_by_id):
    start_number = slot_number_by_id.get(entry.starting_slot_id)
    if start_number is None:
        return []
    return [
        slot_id_by_number[start_number + offset]
        for offset in range(entry.duration)
        if start_number + offset in slot_id_by_number
    ]


def build_busy_slots(entries):
    timeslots = list(Timeslot.objects.order_by("slot_number"))
    slot_id_by_number = {slot.slot_number: slot.slot_id for slot in timeslots}
    slot_number_by_id = {slot.slot_id: slot.slot_number for slot in timeslots}
    queryset = entries.select_related("day", "starting_slot", "assignment__subject", "room").filter(
        status=TimetableEntry.Status.SCHEDULED
    )

    busy = {}
    for entry in queryset:
        day_key = str(entry.day_id)
        busy.setdefault(day_key, {"day_id": entry.day_id, "day_name": entry.day.day_name, "slot_ids": [], "entries": []})
        slot_ids = expanded_slot_ids(entry, slot_id_by_number, slot_number_by_id)
        busy[day_key]["slot_ids"].extend(slot_ids)
        busy[day_key]["entries"].append(
            {
                "entry_id": entry.entry_id,
                "timetable_id": entry.timetable_id,
                "subject_code": entry.assignment.subject_id,
                "room_id": entry.room_id,
                "slot_ids": slot_ids,
            }
        )

    for day in busy.values():
        day["slot_ids"] = sorted(set(day["slot_ids"]))

    return {"count": len(busy), "days": list(busy.values())}


def build_timetable_conflicts(timetable):
    timeslots = list(Timeslot.objects.order_by("slot_number"))
    slot_id_by_number = {slot.slot_number: slot.slot_id for slot in timeslots}
    slot_number_by_id = {slot.slot_id: slot.slot_number for slot in timeslots}
    break_slot_ids = {slot.slot_id for slot in timeslots if slot.is_break}
    entries = list(
        timetable.entries.select_related(
            "assignment__subject",
            "assignment__faculty",
            "assignment__section",
            "day",
            "starting_slot",
            "room",
        ).exclude(status=TimetableEntry.Status.CANCELLED)
    )
    conflicts = []
    occupied = {
        "section": {},
        "faculty": {},
        "room": {},
    }

    for entry in entries:
        slot_ids = expanded_slot_ids(entry, slot_id_by_number, slot_number_by_id)
        if not slot_ids:
            conflicts.append({"type": "invalid_duration", "entry_ids": [entry.entry_id], "detail": "Entry duration extends beyond available timeslots."})
        if break_slot_ids.intersection(slot_ids):
            conflicts.append({"type": "break_slot", "entry_ids": [entry.entry_id], "slot_ids": sorted(break_slot_ids.intersection(slot_ids))})
        if entry.assignment.section_id != timetable.section_id:
            conflicts.append({"type": "section_mismatch", "entry_ids": [entry.entry_id]})
        if entry.assignment.required_room_type != TeachingAssignment.RequiredRoomType.ANY and entry.room.room_type != entry.assignment.required_room_type:
            conflicts.append({"type": "room_type_mismatch", "entry_ids": [entry.entry_id]})
        if entry.room.capacity < entry.assignment.section.student_strength:
            conflicts.append({"type": "room_capacity", "entry_ids": [entry.entry_id]})

        keys = {
            "section": timetable.section_id,
            "faculty": entry.assignment.faculty_id,
            "room": entry.room_id,
        }
        for conflict_type, owner_id in keys.items():
            for slot_id in slot_ids:
                key = (owner_id, entry.day_id, slot_id)
                if key in occupied[conflict_type]:
                    conflicts.append(
                        {
                            "type": f"{conflict_type}_overlap",
                            "entry_ids": [occupied[conflict_type][key], entry.entry_id],
                            "day_id": entry.day_id,
                            "slot_id": slot_id,
                        }
                    )
                occupied[conflict_type][key] = entry.entry_id

    return conflicts


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

    @action(detail=False, methods=["get"], url_path="published")
    def published(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(status=Timetable.Status.PUBLISHED)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})

    @action(detail=False, methods=["get"], url_path=r"sections/(?P<section_id>[^/.]+)/published")
    def section_published(self, request, section_id=None):
        timetable = (
            self.filter_queryset(self.get_queryset())
            .filter(section_id=section_id, status=Timetable.Status.PUBLISHED)
            .order_by("-version_number", "-published_at")
            .first()
        )
        if timetable is None:
            return Response({"detail": "No published timetable found for this section."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(timetable).data)

    @action(detail=False, methods=["get"], url_path=r"faculty/(?P<faculty_id>[^/.]+)")
    def faculty(self, request, faculty_id=None):
        queryset = self.filter_queryset(self.get_queryset()).filter(entries__assignment__faculty_id=faculty_id).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})

    @action(detail=False, methods=["get"], url_path=r"rooms/(?P<room_id>[^/.]+)")
    def room(self, request, room_id=None):
        queryset = self.filter_queryset(self.get_queryset()).filter(entries__room_id=room_id).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})

    @action(detail=False, methods=["get"], url_path=r"departments/(?P<department_id>[^/.]+)")
    def department(self, request, department_id=None):
        queryset = self.filter_queryset(self.get_queryset()).filter(section__department_id=department_id)
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

    @action(detail=True, methods=["get"], url_path="grid")
    def grid(self, request, pk=None):
        timetable = self.get_object()
        entries = (
            timetable.entries.select_related(
                "assignment__subject",
                "assignment__faculty",
                "day",
                "starting_slot",
                "room",
            )
            .filter(status=TimetableEntry.Status.SCHEDULED)
            .order_by("day__day_id", "starting_slot__slot_number")
        )

        results = {}
        for entry in entries:
            day_key = str(entry.day_id)
            slot_key = str(entry.starting_slot_id)
            results.setdefault(
                day_key,
                {
                    "day_id": entry.day_id,
                    "day_name": entry.day.day_name,
                    "slots": {},
                },
            )
            results[day_key]["slots"].setdefault(slot_key, []).append(TimetableEntrySerializer(entry).data)

        return Response(
            {
                "timetable": self.get_serializer(timetable).data,
                "days": list(results.values()),
            }
        )

    @action(detail=True, methods=["get"], url_path="conflicts")
    def conflicts(self, request, pk=None):
        timetable = self.get_object()
        conflicts = build_timetable_conflicts(timetable)
        return Response({"timetable_id": timetable.timetable_id, "conflict_count": len(conflicts), "conflicts": conflicts})

    @action(detail=True, methods=["get"], url_path="export/csv")
    def export_csv(self, request, pk=None):
        timetable = self.get_object()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["day", "slot_number", "duration", "subject_code", "faculty", "room", "entry_type", "status"])
        for entry in timetable.entries.select_related("day", "starting_slot", "assignment__faculty", "room").order_by("day__day_id", "starting_slot__slot_number"):
            writer.writerow(
                [
                    entry.day.day_name,
                    entry.starting_slot.slot_number,
                    entry.duration,
                    entry.assignment.subject_id,
                    entry.assignment.faculty.faculty_name,
                    entry.room.room_name,
                    entry.entry_type,
                    entry.status,
                ]
            )
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="timetable-{timetable.timetable_id}.csv"'
        return response

    @action(detail=True, methods=["get"], url_path="export/ics")
    def export_ics(self, request, pk=None):
        timetable = self.get_object()
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SmartSched//Timetable//EN"]
        for entry in timetable.entries.select_related("day", "starting_slot", "assignment__subject", "assignment__faculty", "room").exclude(status=TimetableEntry.Status.CANCELLED):
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:timetable-{timetable.timetable_id}-entry-{entry.entry_id}@smartsched",
                    f"SUMMARY:{entry.assignment.subject_id} - {entry.assignment.subject.subject_title}",
                    f"DESCRIPTION:Day: {entry.day.day_name}; Slot: {entry.starting_slot.slot_number}; Faculty: {entry.assignment.faculty.faculty_name}",
                    f"LOCATION:{entry.room.room_name}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        response = HttpResponse("\r\n".join(lines), content_type="text/calendar")
        response["Content-Disposition"] = f'attachment; filename="timetable-{timetable.timetable_id}.ics"'
        return response

    @action(detail=True, methods=["get"], url_path="export/pdf")
    def export_pdf(self, request, pk=None):
        return Response(
            {"detail": "PDF export endpoint is reserved; install and configure a PDF renderer to enable it."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


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

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        entries = serializer.save()
        conflicts = []
        for timetable_id in sorted({entry.timetable_id for entry in entries}):
            conflicts.extend(build_timetable_conflicts(Timetable.objects.get(pk=timetable_id)))
        return Response(
            {
                "message": "Timetable entries created successfully.",
                "count": len(entries),
                "entries": self.get_serializer(entries, many=True).data,
                "conflicts": conflicts,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["patch"], url_path="bulk-update")
    def bulk_update(self, request):
        if not isinstance(request.data, list):
            raise serializers.ValidationError({"detail": "Expected a list of entry update objects."})

        updated_entries = []
        for item in request.data:
            entry_id = item.get("entry_id")
            if not entry_id:
                raise serializers.ValidationError({"entry_id": "Each update object must include entry_id."})
            entry = self.get_queryset().get(pk=entry_id)
            serializer = self.get_serializer(entry, data=item, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_entries.append(serializer.save())

        conflicts = []
        for timetable_id in sorted({entry.timetable_id for entry in updated_entries}):
            conflicts.extend(build_timetable_conflicts(Timetable.objects.get(pk=timetable_id)))
        return Response(
            {
                "message": "Timetable entries updated successfully.",
                "count": len(updated_entries),
                "entries": self.get_serializer(updated_entries, many=True).data,
                "conflicts": conflicts,
            }
        )

    @action(detail=False, methods=["get"], url_path=r"faculty/(?P<faculty_id>[^/.]+)/busy-slots")
    def faculty_busy_slots(self, request, faculty_id=None):
        return Response(build_busy_slots(self.filter_queryset(self.get_queryset()).filter(assignment__faculty_id=faculty_id)))

    @action(detail=False, methods=["get"], url_path=r"sections/(?P<section_id>[^/.]+)/busy-slots")
    def section_busy_slots(self, request, section_id=None):
        return Response(build_busy_slots(self.filter_queryset(self.get_queryset()).filter(timetable__section_id=section_id)))

    @action(detail=False, methods=["get"], url_path=r"rooms/(?P<room_id>[^/.]+)/busy-slots")
    def room_busy_slots(self, request, room_id=None):
        return Response(build_busy_slots(self.filter_queryset(self.get_queryset()).filter(room_id=room_id)))

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        entry = self.get_object()
        entry.status = TimetableEntry.Status.CANCELLED
        entry.save(update_fields=["status"])
        return Response({"message": "Timetable entry cancelled successfully.", "entry": self.get_serializer(entry).data})

    @action(detail=True, methods=["post"], url_path="move")
    def move(self, request, pk=None):
        entry = self.get_object()
        serializer = self.get_serializer(entry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(status=TimetableEntry.Status.MODIFIED)
        conflicts = build_timetable_conflicts(entry.timetable)
        return Response({"message": "Timetable entry moved successfully.", "entry": serializer.data, "conflicts": conflicts})

    @action(detail=True, methods=["post"], url_path="substitute")
    def substitute(self, request, pk=None):
        entry = self.get_object()
        payload = {**request.data, "entry_type": TimetableEntry.EntryType.SUBSTITUTE}
        serializer = self.get_serializer(entry, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(status=TimetableEntry.Status.MODIFIED)
        conflicts = build_timetable_conflicts(entry.timetable)
        return Response({"message": "Substitute entry saved successfully.", "entry": serializer.data, "conflicts": conflicts})


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
