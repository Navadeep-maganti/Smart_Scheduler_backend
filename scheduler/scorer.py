from scheduler.constraints import FacultyConstraintIndex
from scheduler.models import SchedulingUnit
from scheduler.occupancy import OccupancyMap


def score_candidate(
    unit: SchedulingUnit,
    day_id: int,
    slot_ids: tuple[int, ...],
    room_by_session_key: dict[str, int],
    occupancy: OccupancyMap,
    faculty_constraints: FacultyConstraintIndex,
    rooms_by_id: dict[int, object],
) -> int:
    score = 0

    for session in unit.sessions:
        room_id = room_by_session_key[session.session_key]
        room = rooms_by_id[room_id]

        if session.preferred_room_id and session.preferred_room_id == room_id:
            score += 15

        score += 10 * faculty_constraints.preferred_count(session.faculty_id, day_id, slot_ids)
        score -= 5 * faculty_constraints.avoid_count(session.faculty_id, day_id, slot_ids)

        current_day_load = occupancy.section_day_load.get((session.section_id, day_id), 0)
        score += max(0, 5 - current_day_load)

        if session.duration > 1 and current_day_load >= 3:
            score -= 10

        spare_capacity = room.capacity - session.student_strength
        score += max(0, min(5, spare_capacity // 10))

    if unit.same_building_required:
        building_ids = {
            rooms_by_id[room_by_session_key[session.session_key]].building_id
            for session in unit.sessions
        }
        if len(building_ids) == 1:
            score += 10

    if unit.preferred_building_id:
        matched = all(
            rooms_by_id[room_by_session_key[session.session_key]].building_id == unit.preferred_building_id
            for session in unit.sessions
        )
        if matched:
            score += 10

    return score
