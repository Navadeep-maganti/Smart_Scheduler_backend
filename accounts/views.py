from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import AppUser, Faculty, Student
from .permissions import CanManageRoles, CanReadUsers, CanWriteUsers, IsActiveAuthenticated
from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    FacultySerializer,
    LogoutSerializer,
    RegisterSerializer,
    RoleSummarySerializer,
    StudentSerializer,
    UpdateUserRoleSerializer,
    UserAdminSerializer,
    UserSerializer,
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


class UserManagementPermission(permissions.BasePermission):
    message = "You do not have permission to manage users."

    def has_permission(self, request, view):
        permission = CanReadUsers() if request.method in permissions.SAFE_METHODS else CanWriteUsers()
        return permission.has_permission(request, view)


class RegisterView(generics.CreateAPIView):
    queryset = AppUser.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response(
            {
                "message": "User registered successfully.",
                "user": response.data,
            },
            status=response.status_code,
            headers=self.get_success_headers(response.data),
        )


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RolePermissionsView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def get(self, request):
        serializer = RoleSummarySerializer(
            {
                "role": request.user.role,
                "permissions": request.user.permissions,
            }
        )
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class UpdateUserRoleView(APIView):
    permission_classes = [CanManageRoles]

    def patch(self, request, user_id):
        user = get_object_or_404(AppUser, user_id=user_id)
        serializer = UpdateUserRoleSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "User role updated successfully.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class UserViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = AppUser.objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [UserManagementPermission]
    success_delete_message = "User deleted successfully."
    filter_map = {
        "role": "role",
        "is_active": "is_active",
    }
    search_fields = ("email",)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        return Response({"message": "User activated successfully.", "user": self.get_serializer(user).data})

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        return Response({"message": "User deactivated successfully.", "user": self.get_serializer(user).data})


class FacultyViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Faculty.objects.select_related("user", "department").all()
    serializer_class = FacultySerializer
    permission_classes = [UserManagementPermission]
    success_delete_message = "Faculty profile deleted successfully."
    filter_map = {
        "department_id": "department_id",
        "user_id": "user_id",
    }
    search_fields = ("faculty_name", "user__email", "department__department_code", "department__department_name")


class StudentViewSet(SafeDestroyMixin, QueryFilterMixin, viewsets.ModelViewSet):
    queryset = Student.objects.select_related("user", "department").all()
    serializer_class = StudentSerializer
    permission_classes = [UserManagementPermission]
    success_delete_message = "Student profile deleted successfully."
    filter_map = {
        "department_id": "department_id",
        "user_id": "user_id",
        "roll_no": "roll_no__iexact",
    }
    search_fields = ("student_name", "roll_no", "user__email", "department__department_code", "department__department_name")


class MeProfileView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def get(self, request):
        if hasattr(request.user, "faculty_profile"):
            return Response({"profile_type": "faculty", "profile": FacultySerializer(request.user.faculty_profile).data})
        if hasattr(request.user, "student_profile"):
            return Response({"profile_type": "student", "profile": StudentSerializer(request.user.student_profile).data})
        return Response({"profile_type": None, "profile": None})

    def patch(self, request):
        if "user" in request.data:
            raise serializers.ValidationError({"user": "You cannot relink your profile."})

        if hasattr(request.user, "faculty_profile"):
            serializer = FacultySerializer(request.user.faculty_profile, data=request.data, partial=True)
        elif hasattr(request.user, "student_profile"):
            serializer = StudentSerializer(request.user.student_profile, data=request.data, partial=True)
        else:
            raise serializers.ValidationError({"detail": "This user does not have a linked profile."})

        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile_type = "faculty" if isinstance(serializer.instance, Faculty) else "student"
        return Response({"profile_type": profile_type, "profile": serializer.data})


class MeTimetableView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def get(self, request):
        from timetables.models import Timetable, TimetableEntry
        from timetables.serializers import TimetableEntrySerializer, TimetableSerializer

        if hasattr(request.user, "student_profile"):
            timetables = Timetable.objects.filter(
                section__department_id=request.user.student_profile.department_id,
                status=Timetable.Status.PUBLISHED,
            )
            entries = TimetableEntry.objects.filter(timetable__in=timetables, status=TimetableEntry.Status.SCHEDULED)
        elif hasattr(request.user, "faculty_profile"):
            entries = TimetableEntry.objects.filter(
                assignment__faculty_id=request.user.faculty_profile.faculty_id,
                status=TimetableEntry.Status.SCHEDULED,
            )
            timetables = Timetable.objects.filter(entries__in=entries).distinct()
        else:
            timetables = Timetable.objects.none()
            entries = TimetableEntry.objects.none()

        return Response(
            {
                "timetables": TimetableSerializer(timetables, many=True).data,
                "entries": TimetableEntrySerializer(entries, many=True).data,
            }
        )


class MeConstraintsView(APIView):
    permission_classes = [IsActiveAuthenticated]

    def get(self, request):
        from constraints.models import FacultyConstraint
        from constraints.serializers import FacultyConstraintSerializer

        if not hasattr(request.user, "faculty_profile"):
            return Response({"count": 0, "results": []})
        queryset = FacultyConstraint.objects.filter(faculty_id=request.user.faculty_profile.faculty_id)
        serializer = FacultyConstraintSerializer(queryset, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})
