from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AppUser, Faculty, Student


class UserSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = AppUser
        fields = ("user_id", "email", "role", "permissions", "is_active", "created_at", "updated_at")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = AppUser
        fields = ("user_id", "email", "password", "role")
        read_only_fields = ("user_id",)

    def validate_email(self, value):
        return AppUser.objects.normalize_email(value)

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return AppUser.objects.create_user(password=password, **validated_data)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = AppUser.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

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


class UserAdminSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
    password = serializers.CharField(write_only=True, min_length=8, required=False)

    class Meta:
        model = AppUser
        fields = ("user_id", "email", "password", "role", "permissions", "is_active", "created_at", "updated_at")
        read_only_fields = ("user_id", "permissions", "created_at", "updated_at")

    def validate_email(self, value):
        return AppUser.objects.normalize_email(value)

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        return AppUser.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class FacultySerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)

    class Meta:
        model = Faculty
        fields = (
            "faculty_id",
            "user",
            "email",
            "role",
            "faculty_name",
            "department",
            "department_code",
            "department_name",
        )
        read_only_fields = ("faculty_id", "email", "role", "department_code", "department_name")

    def validate_user(self, user):
        if user.role not in {AppUser.Role.FACULTY, AppUser.Role.HOD}:
            raise serializers.ValidationError("Selected user must have FACULTY or HOD role.")
        queryset = Faculty.objects.filter(user=user)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Selected user already has a faculty profile.")
        return user


class StudentSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    department_code = serializers.CharField(source="department.department_code", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)

    class Meta:
        model = Student
        fields = (
            "student_id",
            "user",
            "email",
            "role",
            "roll_no",
            "student_name",
            "department",
            "department_code",
            "department_name",
        )
        read_only_fields = ("student_id", "email", "role", "department_code", "department_name")

    def validate_user(self, user):
        if user.role != AppUser.Role.STUDENT:
            raise serializers.ValidationError("Selected user must have STUDENT role.")
        queryset = Student.objects.filter(user=user)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Selected user already has a student profile.")
        return user
