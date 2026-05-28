from collections import Counter

from scheduler.models import SchedulingUnit


def prioritize_units(units: list[SchedulingUnit]) -> list[SchedulingUnit]:
    faculty_load = Counter(
        session.faculty_id
        for unit in units
        for session in unit.sessions
    )

    def priority_key(unit: SchedulingUnit):
        specialized = any(
            session.required_room_type not in {"ANY", "CLASSROOM"}
            for session in unit.sessions
        )
        shared_faculty_pressure = max(faculty_load[session.faculty_id] for session in unit.sessions)
        explicit_priority = 10 - unit.priority_level

        return (
            unit.is_grouped,
            unit.duration,
            specialized,
            shared_faculty_pressure,
            explicit_priority,
            unit.unit_id,
        )

    return sorted(units, key=priority_key, reverse=True)
