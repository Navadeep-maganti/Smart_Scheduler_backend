from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import AcademicTerm, Department, Section, Subject
from accounts.models import AppUser, Faculty, Student
from constraints.models import FacultyConstraint
from infrastructure.models import Room
from timetables.models import SessionGroup, TeachingAssignment, Timetable, TimetableEntry


def choices_payload(choices):
    return [{"value": value, "label": label} for value, label in choices]


class ChoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "roles": choices_payload(AppUser.Role.choices),
                "term_types": choices_payload(AcademicTerm.TermType.choices),
                "subject_types": choices_payload(Subject.SubjectType.choices),
                "room_types": choices_payload(Room.RoomType.choices),
                "required_room_types": choices_payload(TeachingAssignment.RequiredRoomType.choices),
                "session_group_categories": choices_payload(SessionGroup.GroupCategory.choices),
                "timetable_statuses": choices_payload(Timetable.Status.choices),
                "entry_types": choices_payload(TimetableEntry.EntryType.choices),
                "entry_statuses": choices_payload(TimetableEntry.Status.choices),
            }
        )


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_term = AcademicTerm.objects.filter(is_active=True).order_by("-start_date").first()
        payload = {
            "active_term_id": active_term.term_id if active_term else None,
            "departments": Department.objects.count(),
            "sections": Section.objects.count(),
            "subjects": Subject.objects.count(),
            "faculty": Faculty.objects.count(),
            "students": Student.objects.count(),
            "rooms": Room.objects.count(),
            "teaching_assignments": TeachingAssignment.objects.count(),
            "faculty_constraints": FacultyConstraint.objects.count(),
            "timetables": Timetable.objects.count(),
            "published_timetables": Timetable.objects.filter(status=Timetable.Status.PUBLISHED).count(),
            "scheduled_entries": TimetableEntry.objects.filter(status=TimetableEntry.Status.SCHEDULED).count(),
        }
        return Response(payload)
