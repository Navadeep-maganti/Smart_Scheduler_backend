from rest_framework import serializers

from accounts.models import Faculty

from .models import AcademicTerm, Department, Section, Subject


class FacultySummarySerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)

    class Meta:
        model = Faculty
        fields = ("faculty_id", "faculty_name", "email", "role", "department_id")
        read_only_fields = fields


class DepartmentSerializer(serializers.ModelSerializer):
    hod = FacultySummarySerializer(read_only=True)
    hod_id = serializers.PrimaryKeyRelatedField(
        source="hod",
        queryset=Faculty.objects.select_related("user", "department"),
        allow_null=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Department
        fields = (
            "department_id",
            "department_code",
            "department_name",
            "hod",
            "hod_id",
        )
        read_only_fields = ("department_id", "hod")

    def validate_hod_id(self, faculty):
        if faculty is None:
            return faculty
        if faculty.user.role not in {faculty.user.Role.FACULTY, faculty.user.Role.HOD}:
            raise serializers.ValidationError("Selected faculty must have FACULTY or HOD role.")
        return faculty


class AcademicTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicTerm
        fields = (
            "term_id",
            "academic_year",
            "term_type",
            "start_date",
            "end_date",
            "is_active",
        )
        read_only_fields = ("term_id",)

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "End date must be on or after start date."})
        return attrs


class SectionSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)
    academic_year = serializers.CharField(source="academic_term.academic_year", read_only=True)
    term_type = serializers.CharField(source="academic_term.term_type", read_only=True)

    class Meta:
        model = Section
        fields = (
            "section_id",
            "department",
            "department_code",
            "department_name",
            "academic_term",
            "academic_year",
            "term_type",
            "year_number",
            "section_name",
            "student_strength",
        )
        read_only_fields = ("section_id", "department_code", "department_name", "academic_year", "term_type")


class SubjectSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)

    class Meta:
        model = Subject
        fields = (
            "subject_code",
            "subject_title",
            "credits",
            "department",
            "department_code",
            "department_name",
            "subject_type",
            "sessions_per_week",
            "session_duration",
            "required_room_type",
        )
        read_only_fields = ("department_code", "department_name")
