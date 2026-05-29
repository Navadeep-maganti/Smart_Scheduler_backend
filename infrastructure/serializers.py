from rest_framework import serializers

from academics.models import Department

from .models import Building, Day, Room, Timeslot


class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = ("building_id", "building_name")
        read_only_fields = ("building_id",)


class RoomSerializer(serializers.ModelSerializer):
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all(), required=False)
    building_name = serializers.CharField(source="building.building_name", read_only=True)
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)
    building_id = serializers.IntegerField(read_only=True)
    building_name_input = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = Room
        fields = (
            "room_id",
            "room_name",
            "room_type",
            "building",
            "building_id",
            "building_name",
            "building_name_input",
            "capacity",
            "department",
            "department_code",
            "department_name",
        )
        read_only_fields = ("room_id", "building_id", "building_name", "department_code", "department_name")
        validators = []

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be greater than zero.")
        return value

    def validate(self, attrs):
        building_name = attrs.pop("building_name_input", None)
        building = attrs.get("building", getattr(self.instance, "building", None))
        room_name = attrs.get("room_name", getattr(self.instance, "room_name", None))

        if building and building_name:
            raise serializers.ValidationError(
                {"building_name_input": "Provide either building or building_name_input, not both."}
            )

        if building_name:
            try:
                attrs["building"] = Building.objects.get(building_name__iexact=building_name)
            except Building.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"building_name_input": "No building found with this name."}
                ) from exc

        if not attrs.get("building", getattr(self.instance, "building", None)):
            raise serializers.ValidationError({"building": "This field is required."})

        resolved_building = attrs.get("building", getattr(self.instance, "building", None))
        if resolved_building and room_name:
            queryset = Room.objects.filter(building=resolved_building, room_name=room_name)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"room_name": "A room with this name already exists in the selected building."}
                )

        return attrs


class DaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Day
        fields = ("day_id", "day_name")
        read_only_fields = ("day_id",)


class TimeslotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Timeslot
        fields = ("slot_id", "slot_number", "start_time", "end_time", "is_break")
        read_only_fields = ("slot_id",)

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"end_time": "End time must be later than start time."})
        return attrs


class RoomByBuildingRequestSerializer(serializers.Serializer):
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all(), required=False)
    building_name = serializers.CharField(required=False, allow_blank=False)
    room_type = serializers.ChoiceField(choices=Room.RoomType.choices, required=False)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)

    def validate(self, attrs):
        building = attrs.get("building")
        building_name = attrs.get("building_name")

        if building and building_name:
            raise serializers.ValidationError(
                {"building_name": "Provide either building or building_name, not both."}
            )

        if not building and not building_name:
            raise serializers.ValidationError(
                {"building": "Either building or building_name is required."}
            )

        if building_name:
            try:
                attrs["building"] = Building.objects.get(building_name__iexact=building_name)
            except Building.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"building_name": "No building found with this name."}
                ) from exc

        return attrs
