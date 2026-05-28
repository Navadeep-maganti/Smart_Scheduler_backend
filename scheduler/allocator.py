from itertools import count

from scheduler.models import CandidateAllocation, GenerationResult, SchedulingUnit, SessionAllocation
from scheduler.occupancy import OccupancyMap
from scheduler.scorer import score_candidate
from scheduler.utils import ordered_slot_blocks
from scheduler.validator import validate_candidate


class AllocationDeadlock(Exception):
    pass


class TimetableAllocator:
    def __init__(
        self,
        *,
        units: list[SchedulingUnit],
        days: list,
        timeslots: list,
        rooms: list,
        faculty_constraints,
        occupancy: OccupancyMap | None = None,
        candidate_limit_per_unit: int = 25,
        backtrack_step_limit: int = 300,
    ):
        self.units = units
        self.days = days
        self.timeslots = timeslots
        self.rooms = rooms
        self.rooms_by_id = {room.room_id: room for room in rooms}
        self.faculty_constraints = faculty_constraints
        self.candidate_limit_per_unit = candidate_limit_per_unit
        self.backtrack_step_limit = backtrack_step_limit
        self.occupancy = occupancy or OccupancyMap()
        self.allocations: list[SessionAllocation] = []
        self._backtrack_steps = count(1)
        self.failed_unit_index: int | None = None

    def allocate(self) -> GenerationResult:
        try:
            success = self._allocate_unit_at(0)
        except AllocationDeadlock as exc:
            return GenerationResult(
                success=False,
                allocations=self.allocations,
                unscheduled_units=self.units[self.failed_unit_index or 0 :],
                message=str(exc),
            )

        if not success:
            return GenerationResult(
                success=False,
                allocations=self.allocations,
                unscheduled_units=self.units[self.failed_unit_index or 0 :],
                message="Could not find a valid allocation within the bounded backtracking limit.",
            )

        return GenerationResult(
            success=True,
            allocations=self.allocations,
            message=f"Scheduled {len(self.allocations)} session entries.",
        )

    def _allocate_unit_at(self, index: int) -> bool:
        if index >= len(self.units):
            return True

        if next(self._backtrack_steps) > self.backtrack_step_limit:
            raise AllocationDeadlock("Backtracking step limit reached.")

        unit = self.units[index]
        candidates = self.generate_candidates(unit)[: self.candidate_limit_per_unit]
        if not candidates:
            self.failed_unit_index = index
            return False

        for candidate in candidates:
            committed = self._commit(unit, candidate)

            if self._allocate_unit_at(index + 1):
                return True

            for allocation in reversed(committed):
                self.occupancy.release(allocation)
                self.allocations.pop()

        return False

    def generate_candidates(self, unit: SchedulingUnit) -> list[CandidateAllocation]:
        candidates: list[CandidateAllocation] = []
        slot_blocks = ordered_slot_blocks(self.timeslots, unit.duration)

        for day in self.days:
            for slot_ids in slot_blocks:
                for room_by_session_key in self._room_combinations(unit, day.day_id, slot_ids):
                    if not validate_candidate(
                        unit,
                        day.day_id,
                        slot_ids,
                        room_by_session_key,
                        self.occupancy,
                        self.faculty_constraints,
                        self.rooms_by_id,
                    ):
                        continue

                    score = score_candidate(
                        unit,
                        day.day_id,
                        slot_ids,
                        room_by_session_key,
                        self.occupancy,
                        self.faculty_constraints,
                        self.rooms_by_id,
                    )
                    candidates.append(
                        CandidateAllocation(
                            day_id=day.day_id,
                            slot_ids=slot_ids,
                            room_by_session_key=room_by_session_key,
                            score=score,
                        )
                    )

        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.score,
                -candidate.day_id,
                -candidate.slot_ids[0],
            ),
            reverse=True,
        )

    def _room_combinations(
        self,
        unit: SchedulingUnit,
        day_id: int,
        slot_ids: tuple[int, ...],
    ):
        sessions = sorted(
            unit.sessions,
            key=lambda session: (
                session.required_room_type == "CLASSROOM",
                -session.student_strength,
                session.session_key,
            ),
        )

        def room_candidates(session, selected_building_id):
            rooms = []
            for room in self.rooms:
                if selected_building_id and room.building_id != selected_building_id:
                    continue
                if session.required_room_type != "ANY" and room.room_type != session.required_room_type:
                    continue
                if room.capacity < session.student_strength:
                    continue
                if not self.occupancy.is_room_free(room.room_id, day_id, slot_ids):
                    continue

                rooms.append(room)

            return sorted(
                rooms,
                key=lambda room: (
                    session.preferred_room_id != room.room_id,
                    room.capacity,
                    room.room_id,
                ),
            )

        def build(index, selected, selected_room_ids, selected_building_id):
            if index >= len(sessions):
                yield dict(selected)
                return

            session = sessions[index]
            for room in room_candidates(session, selected_building_id):
                if room.room_id in selected_room_ids:
                    continue

                next_building_id = selected_building_id
                if unit.same_building_required:
                    next_building_id = selected_building_id or room.building_id

                selected[session.session_key] = room.room_id
                selected_room_ids.add(room.room_id)

                yield from build(index + 1, selected, selected_room_ids, next_building_id)

                selected_room_ids.remove(room.room_id)
                selected.pop(session.session_key)

        yield from build(0, {}, set(), None)

    def _commit(self, unit: SchedulingUnit, candidate: CandidateAllocation) -> list[SessionAllocation]:
        committed = []

        for session in unit.sessions:
            allocation = SessionAllocation(
                session=session,
                day_id=candidate.day_id,
                starting_slot_id=candidate.slot_ids[0],
                slot_ids=candidate.slot_ids,
                room_id=candidate.room_by_session_key[session.session_key],
            )
            self.occupancy.occupy(allocation)
            self.allocations.append(allocation)
            committed.append(allocation)

        return committed
