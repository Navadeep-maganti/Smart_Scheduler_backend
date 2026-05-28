from scheduler.constraints import FacultyConstraintIndex
from scheduler.models import SchedulingUnit
from scheduler.occupancy import OccupancyMap


def validate_candidate(
    unit: SchedulingUnit,
    day_id: int,
    slot_ids: tuple[int, ...],
    room_by_session_key: dict[str, int],
    occupancy: OccupancyMap,
    faculty_constraints: FacultyConstraintIndex,
    rooms_by_id: dict[int, object],
) -> bool:
    if set(room_by_session_key) != {session.session_key for session in unit.sessions}:
        return False

    candidate_room_slots: set[tuple[int, int, int]] = set()
    candidate_faculty_slots: set[tuple[int, int, int]] = set()
    candidate_section_slots: set[tuple[int, int, int]] = set()

    for session in unit.sessions:
        room_id = room_by_session_key[session.session_key]
        room = rooms_by_id[room_id]

        if session.required_room_type != "ANY" and room.room_type != session.required_room_type:
            return False

        if room.capacity < session.student_strength:
            return False

        if room.department_id and room.department_id != session.department_id:
            return False

        if faculty_constraints.is_unavailable(session.faculty_id, day_id, slot_ids):
            return False

        if not occupancy.can_place(
            session.faculty_id,
            session.section_id,
            room_id,
            day_id,
            slot_ids,
        ):
            return False

        for slot_id in slot_ids:
            room_key = (room_id, day_id, slot_id)
            faculty_key = (session.faculty_id, day_id, slot_id)
            section_key = (session.section_id, day_id, slot_id)

            if room_key in candidate_room_slots:
                return False
            if faculty_key in candidate_faculty_slots:
                return False
            if section_key in candidate_section_slots:
                return False

            candidate_room_slots.add(room_key)
            candidate_faculty_slots.add(faculty_key)
            candidate_section_slots.add(section_key)

    if unit.same_building_required:
        building_ids = {
            rooms_by_id[room_by_session_key[session.session_key]].building_id
            for session in unit.sessions
        }
        if len(building_ids) != 1:
            return False

    return True
