from datetime import time

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser, Faculty
from academics.models import Department
from infrastructure.models import Day, Timeslot

from .models import ConstraintType, FacultyConstraint


class ConstraintsApiTests(APITestCase):
    def setUp(self):
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.department = Department.objects.create(
            department_code="TST",
            department_name="Test Department",
        )
        self.other_department = Department.objects.create(
            department_code="OTH",
            department_name="Other Department",
        )

        self.admin_user = AppUser.objects.create_user(
            email="constraints-admin@example.com",
            password="StrongPass123!",
            role=AppUser.Role.ADMIN,
        )
        self.hod_user = AppUser.objects.create_user(
            email="constraints-hod@example.com",
            password="StrongPass123!",
            role=AppUser.Role.HOD,
        )
        self.faculty_user = AppUser.objects.create_user(
            email="constraints-faculty@example.com",
            password="StrongPass123!",
            role=AppUser.Role.FACULTY,
        )
        self.other_faculty_user = AppUser.objects.create_user(
            email="constraints-other@example.com",
            password="StrongPass123!",
            role=AppUser.Role.FACULTY,
        )
        self.student_user = AppUser.objects.create_user(
            email="constraints-student@example.com",
            password="StrongPass123!",
            role=AppUser.Role.STUDENT,
        )

        self.hod_faculty = Faculty.objects.create(
            user=self.hod_user,
            faculty_name="HOD User",
            department=self.department,
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            faculty_name="Faculty User",
            department=self.department,
        )
        self.other_faculty = Faculty.objects.create(
            user=self.other_faculty_user,
            faculty_name="Other Faculty",
            department=self.other_department,
        )
        self.department.hod = self.hod_faculty
        self.department.save(update_fields=["hod"])

        self.day = Day.objects.create(day_name="Monday")
        self.slot = Timeslot.objects.create(
            slot_number=1,
            start_time=time(9, 0),
            end_time=time(10, 0),
            is_break=False,
        )
        self.constraint_type = ConstraintType.objects.create(
            constraint_name="Unavailable",
            constraint_category="AVAILABILITY",
            priority_level=1,
            is_hard_constraint=True,
            description="Cannot teach during this slot.",
        )
        self.faculty_constraint = FacultyConstraint.objects.create(
            faculty=self.faculty,
            day=self.day,
            slot=self.slot,
            constraint_type=self.constraint_type,
            remarks="Medical appointment",
        )

    def authenticate(self, user):
        response = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_authenticated_user_can_list_constraint_types(self):
        self.authenticate(self.student_user)
        response = self.client.get("/api/constraints/types/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["constraint_name"], "Unavailable")

    def test_admin_can_create_constraint_type(self):
        self.authenticate(self.admin_user)
        response = self.client.post(
            "/api/constraints/types/",
            {
                "constraint_name": "Preferred",
                "constraint_category": "PREFERENCE",
                "priority_level": 3,
                "is_hard_constraint": False,
                "description": "Preferred slot.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_faculty_only_sees_own_constraints(self):
        self.authenticate(self.faculty_user)
        response = self.client.get("/api/constraints/faculty/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["faculty"], self.faculty.faculty_id)

    def test_hod_sees_department_constraints(self):
        self.authenticate(self.hod_user)
        response = self.client.get("/api/constraints/faculty/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_faculty_cannot_create_constraint_for_other_faculty(self):
        self.authenticate(self.faculty_user)
        response = self.client.post(
            "/api/constraints/faculty/",
            {
                "faculty": self.other_faculty.faculty_id,
                "day": self.day.day_id,
                "slot": self.slot.slot_id,
                "constraint_type": self.constraint_type.constraint_type_id,
                "remarks": "Blocked",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_faculty_can_create_own_constraint(self):
        self.authenticate(self.faculty_user)
        other_day = Day.objects.create(day_name="Tuesday")
        response = self.client.post(
            "/api/constraints/faculty/",
            {
                "faculty": self.faculty.faculty_id,
                "day": other_day.day_id,
                "slot": self.slot.slot_id,
                "constraint_type": self.constraint_type.constraint_type_id,
                "remarks": "Blocked",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_can_delete_constraint_type_with_message(self):
        self.authenticate(self.admin_user)
        extra_type = ConstraintType.objects.create(
            constraint_name="Avoid",
            constraint_category="PREFERENCE",
            priority_level=2,
            is_hard_constraint=False,
            description="Avoid slot.",
        )
        response = self.client.delete(f"/api/constraints/types/{extra_type.constraint_type_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Constraint type deleted successfully.")
