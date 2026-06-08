from django.contrib.auth import authenticate, password_validation
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from academics.models import Department, Section
from .models import AppUser, Faculty , Student


class UserSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = AppUser
        fields = ("user_id", "email", "role", "permissions", "is_active", "created_at", "updated_at")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    student_name = serializers.CharField(write_only=True, required=False)
    roll_no = serializers.CharField(write_only=True, required=False)
    faculty_name = serializers.CharField(write_only=True, required=False)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=False,
    )
    section_id = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.select_related("department").all(),
        source="section",
        write_only=True,
        required=False,
    )

    class Meta:
        model = AppUser
        fields = (
            "user_id",
            "email",
            "password",
            "role",
            "student_name",
            "roll_no",
            "faculty_name",
            "department_id",
            "section_id",
        )
        read_only_fields = ("user_id",)

    def validate_email(self, value):
        return AppUser.objects.normalize_email(value)

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate(self, attrs):
        role = attrs.get("role")
        department = attrs.get("department")
        section = attrs.get("section")

        if role == AppUser.Role.STUDENT:
            required_fields = {
                "student_name": "student_name",
                "roll_no": "roll_no",
                "department": "department_id",
                "section": "section_id",
            }
            missing_fields = [
                output_field for internal_field, output_field in required_fields.items() if not attrs.get(internal_field)
            ]
            if missing_fields:
                raise serializers.ValidationError(
                    {field: "This field is required for student registration." for field in missing_fields}
                )
            if section.department_id != department.department_id:
                raise serializers.ValidationError(
                    {"section_id": "Selected section must belong to the selected department."}
                )
        elif role in {AppUser.Role.FACULTY, AppUser.Role.HOD}:
            required_fields = {
                "faculty_name": "faculty_name",
                "department": "department_id",
            }
            missing_fields = [
                output_field for internal_field, output_field in required_fields.items() if not attrs.get(internal_field)
            ]
            if missing_fields:
                raise serializers.ValidationError(
                    {field: "This field is required for faculty registration." for field in missing_fields}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        student_name = validated_data.pop("student_name", None)
        roll_no = validated_data.pop("roll_no", None)
        faculty_name = validated_data.pop("faculty_name", None)
        department = validated_data.pop("department", None)
        section = validated_data.pop("section", None)

        user = AppUser.objects.create_user(password=password, **validated_data)

        if user.role == AppUser.Role.STUDENT:
            Student.objects.create(
                user=user,
                student_name=student_name,
                roll_no=roll_no,
                department=department,
                section=section,
            )
        elif user.role in {AppUser.Role.FACULTY, AppUser.Role.HOD}:
            Faculty.objects.create(
                user=user,
                faculty_name=faculty_name,
                department=department,
            )

        return user


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = AppUser.USERNAME_FIELD
    role = serializers.ChoiceField(choices=AppUser.Role.choices, required=True, write_only=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        role = attrs.get("role")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

        if user.role != role:
            raise AuthenticationFailed("Invalid role for this user.")

        data = super().validate(
            {
                self.username_field: email,
                "password": password,
            }
        )
        data["user"] = UserSerializer(user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        user = self.context["request"].user
        password_validation.validate_password(value, user=user)
        return value

    def validate(self, attrs):
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from the current password."}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            self.token = RefreshToken(value)
        except Exception as exc:
            raise serializers.ValidationError("Refresh token is invalid.") from exc
        return value

    def save(self, **kwargs):
        self.token.blacklist()


class UpdateUserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppUser
        fields = ("user_id", "email", "role", "is_active")
        read_only_fields = ("user_id", "email", "is_active")


class RoleSummarySerializer(serializers.Serializer):
    role = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class FacultySerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)

    class Meta:
        model = Faculty
        fields = (
            "faculty_id",
            "faculty_name",
            "email",
            "role",
            "department_id",
            "department_code",
            "department_name",
        )
    
class StudentSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)
    section_name = serializers.CharField(source="section.section_name", read_only=True)
    section_year = serializers.IntegerField(source="section.year_number", read_only=True)
    
    class Meta:
        model = Student
        fields = (
            "student_id",
            "roll_no",
            "student_name",
            "email",
            "role",
            "department_id",
            "department_code",
            "department_name",
            "section_id",
            "section_name",
            "section_year",
        )
