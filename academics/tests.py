from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser

from .models import AcademicTerm, Department, Section, Subject


class AcademicsApiTests(APITestCase):
    def setUp(self):
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin_user = AppUser.objects.create_user(
            email="academics-admin@example.com",
            password="StrongPass123!",
            role=AppUser.Role.ADMIN,
        )
        self.student_user = AppUser.objects.create_user(
            email="academics-student@example.com",
            password="StrongPass123!",
            role=AppUser.Role.STUDENT,
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
        self.subject = Subject.objects.create(
            subject_code="ECE201",
            subject_title="Signals and Systems",
            credits=4,
            department=self.department,
            subject_type=Subject.SubjectType.THEORY,
            sessions_per_week=3,
            session_duration=1,
            required_room_type=Subject.RequiredRoomType.CLASSROOM,
        )

    def authenticate(self, user):
        login_response = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

    def test_authenticated_user_can_list_departments(self):
        self.authenticate(self.student_user)

        response = self.client.get("/api/academics/departments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["department_code"], "ECE")

    def test_unauthenticated_user_can_list_departments(self):
        response = self.client.get("/api/academics/departments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["department_code"], "ECE")

    def test_invalid_token_user_can_list_departments(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired-or-invalid-token")

        response = self.client.get("/api/academics/departments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["department_code"], "ECE")

    def test_admin_can_create_department(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            "/api/academics/departments/",
            {"department_code": "CSE", "department_name": "Computer Science and Engineering"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Department.objects.filter(department_code="CSE").exists())

    def test_non_admin_cannot_create_department(self):
        self.authenticate(self.student_user)

        response = self.client.post(
            "/api/academics/departments/",
            {"department_code": "ME", "department_name": "Mechanical Engineering"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_filter_sections(self):
        self.authenticate(self.student_user)

        response = self.client.get(f"/api/academics/sections/?department_id={self.department.department_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["section_id"], self.section.section_id)

    def test_unauthenticated_user_can_list_sections(self):
        response = self.client.get(f"/api/academics/sections/?department_id={self.department.department_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["section_id"], self.section.section_id)

    def test_invalid_token_user_can_list_sections(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired-or-invalid-token")

        response = self.client.get(f"/api/academics/sections/?department_id={self.department.department_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["section_id"], self.section.section_id)

    def test_admin_can_update_subject(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            f"/api/academics/subjects/{self.subject.subject_code}/",
            {"subject_title": "Advanced Signals and Systems"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.subject_title, "Advanced Signals and Systems")

    def test_admin_can_delete_term(self):
        self.authenticate(self.admin_user)
        new_term = AcademicTerm.objects.create(
            academic_year="2027-2028",
            term_type=AcademicTerm.TermType.EVEN,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 5, 1),
            is_active=False,
        )

        response = self.client.delete(f"/api/academics/terms/{new_term.term_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AcademicTerm.objects.filter(term_id=new_term.term_id).exists())
