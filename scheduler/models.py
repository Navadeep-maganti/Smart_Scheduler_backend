from dataclasses import dataclass, field


@dataclass(frozen=True)
class SchedulableSession:
    session_key: str
    assignment_id: int
    section_id: int
    faculty_id: int
    department_id: int
    subject_code: str
    subject_type: str
    required_room_type: str
    preferred_room_id: int | None
    duration: int
    student_strength: int
    assignment_priority: int


@dataclass(frozen=True)
class SchedulingUnit:
    unit_id: str
    sessions: tuple[SchedulableSession, ...]
    is_grouped: bool = False
    group_id: int | None = None
    same_time_required: bool = True
    same_building_required: bool = False
    preferred_building_id: int | None = None
    priority_level: int = 3

    @property
    def duration(self) -> int:
        return max(session.duration for session in self.sessions)


@dataclass(frozen=True)
class CandidateAllocation:
    day_id: int
    slot_ids: tuple[int, ...]
    room_by_session_key: dict[str, int]
    score: int


@dataclass(frozen=True)
class SessionAllocation:
    session: SchedulableSession
    day_id: int
    starting_slot_id: int
    slot_ids: tuple[int, ...]
    room_id: int


@dataclass
class GenerationResult:
    success: bool
    allocations: list[SessionAllocation] = field(default_factory=list)
    unscheduled_units: list[SchedulingUnit] = field(default_factory=list)
    message: str = ""
