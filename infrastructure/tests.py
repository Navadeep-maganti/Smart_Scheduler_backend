from datetime import time

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AppUser
from academics.models import Department
from timetables.models import Timetable, TimetableEntry, TeachingAssignment

from .models import Building, Day, Room, Timeslot


class InfrastructureApiTests(APITestCase):
    def setUp(self):
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin_user = AppUser.objects.create_user(
            email="infra-admin@example.com",
            password="StrongPass123!",
            role=AppUser.Role.ADMIN,
        )
        self.student_user = AppUser.objects.create_user(
            email="infra-student@example.com",
            password="StrongPass123!",
            role=AppUser.Role.STUDENT,
        )
        self.department = Department.objects.create(
            department_code="INF",
            department_name="Infrastructure Test Department",
        )
        self.building = Building.objects.create(building_name="Main Block")
        self.day = Day.objects.create(day_name="Saturday")
        self.timeslot = Timeslot.objects.create(
            slot_number=90,
            start_time=time(8, 0),
            end_time=time(9, 0),
            is_break=False,
        )
        self.room = Room.objects.create(
            room_name="101",
            room_type=Room.RoomType.CLASSROOM,
            building=self.building,
            capacity=60,
            department=self.department,
        )
        self.second_room = Room.objects.create(
            room_name="102",
            room_type=Room.RoomType.CLASSROOM,
            building=self.building,
            capacity=55,
            department=self.department,
        )

    def authenticate(self, user):
        response = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_authenticated_user_can_list_rooms(self):
        self.authenticate(self.student_user)
        response = self.client.get("/api/infrastructure/rooms/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["room_name"], "101")

    def test_admin_can_create_building(self):
        self.authenticate(self.admin_user)
        response = self.client.post(
            "/api/infrastructure/buildings/",
            {"building_name": "Science Block"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_admin_cannot_create_room(self):
        self.authenticate(self.student_user)
        response = self.client.post(
            "/api/infrastructure/rooms/",
            {
                "room_name": "102",
                "room_type": "CLASSROOM",
                "building": self.building.building_id,
                "capacity": 45,
                "department": self.department.department_id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_filter_timeslots(self):
        self.authenticate(self.student_user)
        response = self.client.get("/api/infrastructure/timeslots/?slot_number=90")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["slot_number"], 90)

    def test_admin_delete_returns_message(self):
        self.authenticate(self.admin_user)
        delete_day = Day.objects.create(day_name="Sunday")
        response = self.client.delete(f"/api/infrastructure/days/{delete_day.day_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Day deleted successfully.")

    def test_admin_can_create_room_with_building_name_input(self):
        self.authenticate(self.admin_user)
        response = self.client.post(
            "/api/infrastructure/rooms/",
            {
                "room_name": "103",
                "room_type": "CLASSROOM",
                "building_name_input": "Main Block",
                "capacity": 48,
                "department": self.department.department_id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["building_name"], "Main Block")

    def test_available_rooms_endpoint_filters_by_day_and_slot(self):
        self.authenticate(self.admin_user)
        term = self.department.sections.model._meta.get_field("academic_term").remote_field.model.objects.create(
            academic_year="2032-2033",
            term_type="ODD",
            start_date="2032-06-01",
            end_date="2032-11-01",
            is_active=True,
        )
        section = self.department.sections.model.objects.create(
            department=self.department,
            academic_term=term,
            year_number=1,
            section_name="A",
            student_strength=50,
        )
        faculty_user = AppUser.objects.create_user(
            email="infra-faculty@example.com",
            password="StrongPass123!",
            role=AppUser.Role.FACULTY,
        )
        faculty = self.department.faculty.model.objects.create(
            user=faculty_user,
            faculty_name="Infra Faculty",
            department=self.department,
        )
        subject = self.department.subjects.model.objects.create(
            subject_code="INF101",
            subject_title="Infrastructure Basics",
            credits=3,
            department=self.department,
            subject_type="THEORY",
            sessions_per_week=3,
            session_duration=1,
            required_room_type="CLASSROOM",
        )
        assignment = TeachingAssignment.objects.create(
            section=section,
            subject=subject,
            faculty=faculty,
            required_room_type="CLASSROOM",
        )
        timetable = Timetable.objects.create(section=section, term=term, version_number=1, status="GENERATED")
        TimetableEntry.objects.create(
            timetable=timetable,
            assignment=assignment,
            day=self.day,
            starting_slot=self.timeslot,
            duration=1,
            room=self.room,
            status="SCHEDULED",
        )

        response = self.client.get(
            f"/api/infrastructure/rooms/available/?day_id={self.day.day_id}&slot_id={self.timeslot.slot_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["room_id"], self.second_room.room_id)

    def test_available_timeslots_endpoint_returns_available_room_counts(self):
        self.authenticate(self.admin_user)
        response = self.client.get(f"/api/infrastructure/timeslots/available/?day_id={self.day.day_id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIn("available_room_count", response.data["results"][0])

    def test_can_get_rooms_by_building_from_body(self):
        self.authenticate(self.student_user)
        response = self.client.get(
            "/api/infrastructure/rooms/by-building/?building_name=Main Block",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["building_name"], "Main Block")
        self.assertEqual(response.data["count"], 2)
