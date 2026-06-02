from rest_framework import generics, permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import AppUser, Faculty, Student
from .permissions import CanManageRoles, IsActiveAuthenticated
from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    FacultySerializer,
    StudentSerializer,
    LogoutSerializer,
    RegisterSerializer,
    RoleSummarySerializer,
    UpdateUserRoleSerializer,
    UserSerializer,
)


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


class FacultyListView(generics.ListAPIView):
    queryset = Faculty.objects.select_related("user", "department").all()
    permission_classes = [IsActiveAuthenticated]
    serializer_class = FacultySerializer

class StudentListView(generics.ListAPIView):
    queryset = Student.objects.select_related("user", "department").all()
    permission_classes = [IsActiveAuthenticated]
    serializer_class = StudentSerializer

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
