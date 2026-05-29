from rest_framework import serializers

from accounts.models import Faculty
from infrastructure.models import Day, Timeslot

from .models import ConstraintType, FacultyConstraint


class ConstraintTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConstraintType
        fields = (
            "constraint_type_id",
            "constraint_name",
            "constraint_category",
            "priority_level",
            "is_hard_constraint",
            "description",
        )
        read_only_fields = ("constraint_type_id",)


class FacultyConstraintSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source="faculty.faculty_name", read_only=True)
    faculty_department_id = serializers.IntegerField(source="faculty.department_id", read_only=True)
    day_name = serializers.CharField(source="day.day_name", read_only=True)
    slot_number = serializers.IntegerField(source="slot.slot_number", read_only=True)
    constraint_type_name = serializers.CharField(source="constraint_type.constraint_name", read_only=True)

    class Meta:
        model = FacultyConstraint
        fields = (
            "constraint_id",
            "faculty",
            "faculty_name",
            "faculty_department_id",
            "day",
            "day_name",
            "slot",
            "slot_number",
            "constraint_type",
            "constraint_type_name",
            "remarks",
        )
        read_only_fields = (
            "constraint_id",
            "faculty_name",
            "faculty_department_id",
            "day_name",
            "slot_number",
            "constraint_type_name",
        )

    def validate(self, attrs):
        faculty = attrs.get("faculty", getattr(self.instance, "faculty", None))
        day = attrs.get("day", getattr(self.instance, "day", None))
        slot = attrs.get("slot", getattr(self.instance, "slot", None))

        if faculty and faculty.user.role not in {faculty.user.Role.FACULTY, faculty.user.Role.HOD}:
            raise serializers.ValidationError({"faculty": "Selected faculty must have FACULTY or HOD role."})

        if day and slot and getattr(slot, "is_break", False):
            raise serializers.ValidationError({"slot": "Break timeslots cannot be used for faculty constraints."})

        return attrs
