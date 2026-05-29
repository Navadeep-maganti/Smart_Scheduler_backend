from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from timetables.models import TimetableEntry

from .models import Building, Day, Room, Timeslot
from .permissions import InfrastructurePermission
from .serializers import (
    BuildingSerializer,
    DaySerializer,
    RoomByBuildingRequestSerializer,
    RoomSerializer,
    TimeslotSerializer,
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


class AvailabilityMixin:
    def _timeslot_maps(self):
        timeslots = list(Timeslot.objects.order_by("slot_number"))
        slot_id_by_number = {slot.slot_number: slot.slot_id for slot in timeslots}
        slot_number_by_id = {slot.slot_id: slot.slot_number for slot in timeslots}
        return timeslots, slot_id_by_number, slot_number_by_id

    def _occupied_room_slots(self, day_id, room_queryset):
        _, slot_id_by_number, slot_number_by_id = self._timeslot_maps()
        occupied_by_room = {room_id: set() for room_id in room_queryset.values_list("room_id", flat=True)}
        entries = (
            TimetableEntry.objects.filter(day_id=day_id, status=TimetableEntry.Status.SCHEDULED, room__in=room_queryset)
            .select_related("starting_slot")
        )
        for entry in entries:
            start_number = slot_number_by_id[entry.starting_slot_id]
            for offset in range(entry.duration):
                slot_id = slot_id_by_number.get(start_number + offset)
                if slot_id:
                    occupied_by_room.setdefault(entry.room_id, set()).add(slot_id)
        return occupied_by_room


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


class BuildingViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = [InfrastructurePermission]
    success_delete_message = "Building deleted successfully."
    search_fields = ("building_name",)


class RoomViewSet(AvailabilityMixin, SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Room.objects.select_related("building", "department").all()
    serializer_class = RoomSerializer
    permission_classes = [InfrastructurePermission]
    success_delete_message = "Room deleted successfully."
    filter_map = {
        "building_id": "building_id",
        "department_id": "department_id",
        "room_type": "room_type",
    }
    search_fields = ("room_name", "building__building_name", "department__department_code", "department__department_name")

    @action(detail=False, methods=["get"], url_path="by-building")
    def by_building(self, request):
        request_serializer = RoomByBuildingRequestSerializer(data=request.query_params)
        request_serializer.is_valid(raise_exception=True)

        building = request_serializer.validated_data["building"]
        queryset = self.get_queryset().filter(building=building)

        room_type = request_serializer.validated_data.get("room_type")
        department = request_serializer.validated_data.get("department")

        if room_type:
            queryset = queryset.filter(room_type=room_type)
        if "department" in request_serializer.validated_data:
            queryset = queryset.filter(department=department)

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "building_id": building.building_id,
                "building_name": building.building_name,
                "count": len(serializer.data),
                "results": serializer.data,
            }
        )

    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        day_id = request.query_params.get("day_id")
        if not day_id:
            raise serializers.ValidationError({"day_id": "This query parameter is required."})

        Day.objects.get(pk=day_id)
        queryset = self.filter_queryset(self.get_queryset())
        slot_id = request.query_params.get("slot_id")
        timeslots, _, _ = self._timeslot_maps()
        occupied_by_room = self._occupied_room_slots(day_id, queryset)

        if slot_id:
            available_rooms = []
            for room in queryset:
                if int(slot_id) not in occupied_by_room.get(room.room_id, set()):
                    room_data = self.get_serializer(room).data
                    room_data["available_for_slot_id"] = int(slot_id)
                    available_rooms.append(room_data)
            return Response(
                {
                    "day_id": int(day_id),
                    "slot_id": int(slot_id),
                    "count": len(available_rooms),
                    "results": available_rooms,
                }
            )

        slot_ids = [slot.slot_id for slot in timeslots]
        results = []
        for room in queryset:
            occupied_slot_ids = sorted(occupied_by_room.get(room.room_id, set()))
            available_slot_ids = [slot_id_value for slot_id_value in slot_ids if slot_id_value not in occupied_slot_ids]
            room_data = self.get_serializer(room).data
            room_data["occupied_slot_ids"] = occupied_slot_ids
            room_data["available_slot_ids"] = available_slot_ids
            results.append(room_data)

        return Response(
            {
                "day_id": int(day_id),
                "count": len(results),
                "results": results,
            }
        )


class DayViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Day.objects.all()
    serializer_class = DaySerializer
    permission_classes = [InfrastructurePermission]
    success_delete_message = "Day deleted successfully."
    search_fields = ("day_name",)


class TimeslotViewSet(AvailabilityMixin, SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Timeslot.objects.all()
    serializer_class = TimeslotSerializer
    permission_classes = [InfrastructurePermission]
    success_delete_message = "Timeslot deleted successfully."
    filter_map = {
        "is_break": "is_break",
        "slot_number": "slot_number",
    }

    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        day_id = request.query_params.get("day_id")
        if not day_id:
            raise serializers.ValidationError({"day_id": "This query parameter is required."})

        Day.objects.get(pk=day_id)
        room_queryset = Room.objects.select_related("building", "department").all()
        room_type = request.query_params.get("room_type")
        building_id = request.query_params.get("building_id")
        department_id = request.query_params.get("department_id")
        room_id = request.query_params.get("room_id")

        if room_type:
            room_queryset = room_queryset.filter(room_type=room_type)
        if building_id:
            room_queryset = room_queryset.filter(building_id=building_id)
        if department_id:
            room_queryset = room_queryset.filter(department_id=department_id)
        if room_id:
            room_queryset = room_queryset.filter(room_id=room_id)

        timeslots = list(self.filter_queryset(self.get_queryset()))
        occupied_by_room = self._occupied_room_slots(day_id, room_queryset)
        all_room_ids = list(room_queryset.values_list("room_id", flat=True))

        results = []
        for timeslot in timeslots:
            available_room_ids = [
                current_room_id
                for current_room_id in all_room_ids
                if timeslot.slot_id not in occupied_by_room.get(current_room_id, set())
            ]
            results.append(
                {
                    **self.get_serializer(timeslot).data,
                    "available_room_ids": available_room_ids,
                    "available_room_count": len(available_room_ids),
                }
            )

        return Response(
            {
                "day_id": int(day_id),
                "room_count": len(all_room_ids),
                "count": len(results),
                "results": results,
            }
        )
