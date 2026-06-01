from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AppUser, Faculty


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
    