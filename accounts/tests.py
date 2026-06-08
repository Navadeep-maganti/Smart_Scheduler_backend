from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from academics.models import AcademicTerm, Department, Section

from .models import AppUser, Faculty, Student


class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.password = "StrongPass123!"
        self.user = AppUser.objects.create_user(
            email="user@example.com",
            password=self.password,
            role=AppUser.Role.ADMIN,
        )
        self.department = Department.objects.create(
            department_code="ECE",
            department_name="Electronics and Communication Engineering",
        )
        self.term = AcademicTerm.objects.create(
            academic_year="2026-2027",
            term_type=AcademicTerm.TermType.ODD,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 11, 1),
            is_active=True,
        )
        self.section = Section.objects.create(
            department=self.department,
            academic_term=self.term,
            year_number=2,
            section_name="A",
            student_strength=60,
        )

    def authenticate(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password, "role": self.user.role},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response

    def test_register_returns_user_payload(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "newuser@example.com",
                "password": "AnotherPass123!",
                "role": AppUser.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "User registered successfully.")
        self.assertEqual(response.data["user"]["email"], "newuser@example.com")
        self.assertTrue(AppUser.objects.filter(email="newuser@example.com").exists())

    def test_register_creates_student_profile(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "student@example.com",
                "password": "AnotherPass123!",
                "role": AppUser.Role.STUDENT,
                "student_name": "Student One",
                "roll_no": "ECE001",
                "department_id": self.department.department_id,
                "section_id": self.section.section_id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = AppUser.objects.get(email="student@example.com")
        student = Student.objects.get(user=user)
        self.assertEqual(student.student_name, "Student One")
        self.assertEqual(student.roll_no, "ECE001")
        self.assertEqual(student.department_id, self.department.department_id)
        self.assertEqual(student.section_id, self.section.section_id)

    def test_register_creates_faculty_profile(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "faculty@example.com",
                "password": "AnotherPass123!",
                "role": AppUser.Role.FACULTY,
                "faculty_name": "Faculty One",
                "department_id": self.department.department_id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = AppUser.objects.get(email="faculty@example.com")
        faculty = Faculty.objects.get(user=user)
        self.assertEqual(faculty.faculty_name, "Faculty One")
        self.assertEqual(faculty.department_id, self.department.department_id)

    def test_register_rejects_student_without_profile_details(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "incomplete-student@example.com",
                "password": "AnotherPass123!",
                "role": AppUser.Role.STUDENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("student_name", response.data)
        self.assertIn("roll_no", response.data)
        self.assertIn("department_id", response.data)
        self.assertIn("section_id", response.data)

    def test_register_rejects_faculty_without_profile_details(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "incomplete-faculty@example.com",
                "password": "AnotherPass123!",
                "role": AppUser.Role.FACULTY,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("faculty_name", response.data)
        self.assertIn("department_id", response.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {"email": "weak@example.com", "password": "12345678", "role": AppUser.Role.STUDENT},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_returns_tokens_and_user(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password, "role": self.user.role},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["user_id"], self.user.user_id)

    def test_login_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password, "role": self.user.role},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_accepts_matching_role(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "email": self.user.email,
                "password": self.password,
                "role": AppUser.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], AppUser.Role.ADMIN)

    def test_login_rejects_role_mismatch(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "email": self.user.email,
                "password": self.password,
                "role": AppUser.Role.STUDENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_requires_role(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_returns_authenticated_user(self):
        self.authenticate()

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertIn("permissions", response.data)

    def test_change_password_updates_credentials(self):
        self.authenticate()

        response = self.client.post(
            "/api/auth/change-password/",
            {"current_password": self.password, "new_password": "UpdatedPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("UpdatedPass123!"))

    def test_logout_blacklists_refresh_token(self):
        login_response = self.authenticate()

        response = self.client.post(
            "/api/auth/logout/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_tokens(self):
        login_response = self.authenticate()

        response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_permissions_endpoint_returns_role_permissions(self):
        self.authenticate()

        response = self.client.get("/api/auth/permissions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], self.user.role)
        self.assertIn("auth:manage_roles", response.data["permissions"])

    def test_admin_can_update_user_role(self):
        self.authenticate()
        target_user = AppUser.objects.create_user(
            email="target@example.com",
            password="StrongPass123!",
            role=AppUser.Role.STUDENT,
        )

        response = self.client.patch(
            f"/api/auth/users/{target_user.user_id}/role/",
            {"role": AppUser.Role.FACULTY},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertEqual(target_user.role, AppUser.Role.FACULTY)
        self.assertEqual(response.data["user"]["role"], AppUser.Role.FACULTY)

    def test_non_admin_cannot_update_user_role(self):
        self.user.role = AppUser.Role.FACULTY
        self.user.save(update_fields=["role"])
        self.authenticate()
        target_user = AppUser.objects.create_user(
            email="blocked@example.com",
            password="StrongPass123!",
            role=AppUser.Role.STUDENT,
        )

        response = self.client.patch(
            f"/api/auth/users/{target_user.user_id}/role/",
            {"role": AppUser.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
