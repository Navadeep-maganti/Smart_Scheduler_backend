from collections import defaultdict

from accounts.models import Faculty
from constraints.models import FacultyConstraint
from infrastructure.models import Day, Room, Timeslot
from scheduler.constraints import FacultyConstraintIndex
from scheduler.models import SchedulableSession, SchedulingUnit
from timetables.models import SessionGroupMember, TeachingAssignment


class SchedulerData:
    def __init__(
        self,
        *,
        days,
        timeslots,
        rooms,
        assignments,
        grouped_units,
        ungrouped_units,
        faculty_constraints,
    ):
        self.days = days
        self.timeslots = timeslots
        self.rooms = rooms
        self.assignments = assignments
        self.units = grouped_units + ungrouped_units
        self.faculty_constraints = faculty_constraints


def load_scheduler_data(term_id: int, section_ids: list[int] | None = None) -> SchedulerData:
    assignments = TeachingAssignment.objects.filter(section__academic_term_id=term_id).select_related(
        "section",
        "subject",
        "faculty",
        "preferred_room",
    )
    if section_ids:
        assignments = assignments.filter(section_id__in=section_ids)

    assignments = list(assignments.order_by("assignment_id"))
    faculty_ids = [assignment.faculty_id for assignment in assignments]
    faculty_constraints = FacultyConstraintIndex.from_queryset(
        FacultyConstraint.objects.filter(faculty_id__in=faculty_ids).select_related("constraint_type")
    )

    sessions = expand_assignments(assignments)
    grouped_units, grouped_session_keys = build_grouped_units(assignments, sessions)
    ungrouped_units = [
        SchedulingUnit(unit_id=f"session:{session.session_key}", sessions=(session,))
        for session in sessions
        if session.session_key not in grouped_session_keys
    ]

    return SchedulerData(
        days=list(Day.objects.order_by("day_id")),
        timeslots=list(Timeslot.objects.order_by("slot_number")),
        rooms=list(Room.objects.select_related("building").order_by("room_id")),
        assignments=assignments,
        grouped_units=grouped_units,
        ungrouped_units=ungrouped_units,
        faculty_constraints=faculty_constraints,
    )


def expand_assignments(assignments: list[TeachingAssignment]) -> list[SchedulableSession]:
    sessions = []

    for assignment in assignments:
        subject = assignment.subject
        required_room_type = assignment.required_room_type
        if required_room_type == TeachingAssignment.RequiredRoomType.ANY:
            required_room_type = subject.required_room_type

        for occurrence in range(subject.sessions_per_week):
            sessions.append(
                SchedulableSession(
                    session_key=f"{assignment.assignment_id}:{occurrence + 1}",
                    assignment_id=assignment.assignment_id,
                    section_id=assignment.section_id,
                    faculty_id=assignment.faculty_id,
                    department_id=assignment.section.department_id,
                    subject_code=assignment.subject_id,
                    subject_type=subject.subject_type,
                    required_room_type=required_room_type,
                    preferred_room_id=assignment.preferred_room_id,
                    duration=subject.session_duration,
                    student_strength=assignment.section.student_strength,
                    assignment_priority=assignment.priority_level,
                )
            )

    return sessions


def build_grouped_units(
    assignments: list[TeachingAssignment],
    sessions: list[SchedulableSession],
) -> tuple[list[SchedulingUnit], set[str]]:
    assignment_ids = [assignment.assignment_id for assignment in assignments]
    members = list(
        SessionGroupMember.objects.filter(assignment_id__in=assignment_ids)
        .select_related("group")
        .order_by("group_id", "assignment_id")
    )
    group_by_assignment = {member.assignment_id: member.group for member in members}
    sessions_by_assignment = defaultdict(list)

    for session in sessions:
        sessions_by_assignment[session.assignment_id].append(session)

    grouped_units = []
    grouped_session_keys: set[str] = set()
    assignments_by_group = defaultdict(list)

    for assignment in assignments:
        group = group_by_assignment.get(assignment.assignment_id)
        if group:
            assignments_by_group[group.group_id].append(assignment)

    for group_id, grouped_assignments in sorted(assignments_by_group.items()):
        group = group_by_assignment[grouped_assignments[0].assignment_id]
        max_occurrences = max(len(sessions_by_assignment[assignment.assignment_id]) for assignment in grouped_assignments)

        for occurrence in range(max_occurrences):
            grouped_sessions = tuple(
                sessions_by_assignment[assignment.assignment_id][occurrence]
                for assignment in grouped_assignments
                if occurrence < len(sessions_by_assignment[assignment.assignment_id])
            )
            if not grouped_sessions:
                continue

            grouped_session_keys.update(session.session_key for session in grouped_sessions)
            grouped_units.append(
                SchedulingUnit(
                    unit_id=f"group:{group_id}:{occurrence + 1}",
                    sessions=grouped_sessions,
                    is_grouped=True,
                    group_id=group_id,
                    same_time_required=group.same_time_required,
                    same_building_required=group.same_building_required,
                    preferred_building_id=group.preferred_building_id,
                    priority_level=group.priority_level,
                )
            )

    return grouped_units, grouped_session_keys
