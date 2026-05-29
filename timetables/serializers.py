from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from academics.models import AcademicTerm, Section

from .models import SessionGroup, SessionGroupMember, TeachingAssignment, Timetable, TimetableEntry


class TeachingAssignmentSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.section_name", read_only=True)
    subject_title = serializers.CharField(source="subject.subject_title", read_only=True)
    faculty_name = serializers.CharField(source="faculty.faculty_name", read_only=True)
    preferred_room_name = serializers.CharField(source="preferred_room.room_name", read_only=True)

    class Meta:
        model = TeachingAssignment
        fields = (
            "assignment_id",
            "section",
            "section_name",
            "subject",
            "subject_title",
            "faculty",
            "faculty_name",
            "required_room_type",
            "preferred_room",
            "preferred_room_name",
            "priority_level",
        )
        read_only_fields = ("assignment_id", "section_name", "subject_title", "faculty_name", "preferred_room_name")

    def validate(self, attrs):
        instance = TeachingAssignment(**{**getattr(self.instance, "__dict__", {}), **attrs})
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class SessionGroupMemberNestedSerializer(serializers.ModelSerializer):
    assignment_subject_code = serializers.CharField(source="assignment.subject_id", read_only=True)

    class Meta:
        model = SessionGroupMember
        fields = ("group_member_id", "assignment", "assignment_subject_code")
        read_only_fields = fields


class SessionGroupSerializer(serializers.ModelSerializer):
    preferred_building_name = serializers.CharField(source="preferred_building.building_name", read_only=True)
    members = SessionGroupMemberNestedSerializer(many=True, read_only=True)

    class Meta:
        model = SessionGroup
        fields = (
            "group_id",
            "group_name",
            "group_category",
            "same_time_required",
            "same_building_required",
            "preferred_building",
            "preferred_building_name",
            "priority_level",
            "members",
        )
        read_only_fields = ("group_id", "preferred_building_name", "members")


class SessionGroupMemberSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.group_name", read_only=True)
    assignment_subject_code = serializers.CharField(source="assignment.subject_id", read_only=True)

    class Meta:
        model = SessionGroupMember
        fields = (
            "group_member_id",
            "group",
            "group_name",
            "assignment",
            "assignment_subject_code",
        )
        read_only_fields = ("group_member_id", "group_name", "assignment_subject_code")


class TimetableSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.section_name", read_only=True)
    term_label = serializers.SerializerMethodField()
    generated_by_email = serializers.CharField(source="generated_by.email", read_only=True)

    class Meta:
        model = Timetable
        fields = (
            "timetable_id",
            "section",
            "section_name",
            "term",
            "term_label",
            "version_number",
            "status",
            "generated_at",
            "generated_by",
            "generated_by_email",
            "published_at",
        )
        read_only_fields = ("timetable_id", "section_name", "term_label", "generated_at", "generated_by_email")

    def get_term_label(self, obj):
        return str(obj.term)

    def validate(self, attrs):
        data = {}
        if self.instance is not None:
            for field in ("section", "term", "version_number", "status", "generated_at", "generated_by", "published_at"):
                data[field] = getattr(self.instance, field)
        data.update(attrs)
        instance = Timetable(**data)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class TimetableEntrySerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="assignment.subject_id", read_only=True)
    faculty_name = serializers.CharField(source="assignment.faculty.faculty_name", read_only=True)
    room_name = serializers.CharField(source="room.room_name", read_only=True)
    day_name = serializers.CharField(source="day.day_name", read_only=True)
    starting_slot_number = serializers.IntegerField(source="starting_slot.slot_number", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = (
            "entry_id",
            "timetable",
            "assignment",
            "subject_code",
            "faculty_name",
            "day",
            "day_name",
            "starting_slot",
            "starting_slot_number",
            "duration",
            "room",
            "room_name",
            "entry_type",
            "status",
            "created_at",
        )
        read_only_fields = (
            "entry_id",
            "subject_code",
            "faculty_name",
            "day_name",
            "starting_slot_number",
            "room_name",
            "created_at",
        )

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than zero.")
        return value

    def validate(self, attrs):
        data = {}
        if self.instance is not None:
            for field in ("timetable", "assignment", "day", "starting_slot", "duration", "room", "entry_type", "status"):
                data[field] = getattr(self.instance, field)
        data.update(attrs)
        instance = TimetableEntry(**data)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class SchedulerRequestSerializer(serializers.Serializer):
    term_id = serializers.PrimaryKeyRelatedField(queryset=AcademicTerm.objects.all(), source="term")
    section_ids = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.select_related("department", "academic_term").all(),
        source="sections",
        many=True,
        required=False,
    )
    locked_timetable_ids = serializers.PrimaryKeyRelatedField(
        queryset=Timetable.objects.all(),
        source="locked_timetables",
        many=True,
        required=False,
    )

    def validate(self, attrs):
        term = attrs["term"]
        sections = attrs.get("sections", [])
        locked_timetables = attrs.get("locked_timetables", [])

        for section in sections:
            if section.academic_term_id != term.term_id:
                raise serializers.ValidationError(
                    {"section_ids": f"Section {section.section_id} does not belong to the selected term."}
                )

        for timetable in locked_timetables:
            if timetable.term_id != term.term_id:
                raise serializers.ValidationError(
                    {"locked_timetable_ids": f"Timetable {timetable.timetable_id} does not belong to the selected term."}
                )

        return attrs


class SchedulerRegenerateSerializer(SchedulerRequestSerializer):
    archive_timetable_ids = serializers.PrimaryKeyRelatedField(
        queryset=Timetable.objects.all(),
        source="archive_timetables",
        many=True,
        required=False,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        term = attrs["term"]
        archive_timetables = attrs.get("archive_timetables", [])
        for timetable in archive_timetables:
            if timetable.term_id != term.term_id:
                raise serializers.ValidationError(
                    {"archive_timetable_ids": f"Timetable {timetable.timetable_id} does not belong to the selected term."}
                )
        return attrs


class SchedulerAllocationSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField()
    section_id = serializers.IntegerField()
    faculty_id = serializers.IntegerField()
    subject_code = serializers.CharField()
    day_id = serializers.IntegerField()
    starting_slot_id = serializers.IntegerField()
    slot_ids = serializers.ListField(child=serializers.IntegerField())
    room_id = serializers.IntegerField()


class SchedulerResultSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    allocation_count = serializers.IntegerField()
    unscheduled_count = serializers.IntegerField()
    allocations = SchedulerAllocationSerializer(many=True)
    unscheduled_units = serializers.ListField(child=serializers.CharField())
    created_timetable_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
