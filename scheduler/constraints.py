from collections import defaultdict

from scheduler.utils import constraint_name


class FacultyConstraintIndex:
    def __init__(self):
        self.unavailable: set[tuple[int, int, int]] = set()
        self.preferred: set[tuple[int, int, int]] = set()
        self.avoid: set[tuple[int, int, int]] = set()
        self.by_faculty: dict[int, list] = defaultdict(list)

    @classmethod
    def from_queryset(cls, faculty_constraints):
        index = cls()

        for constraint in faculty_constraints:
            key = (constraint.faculty_id, constraint.day_id, constraint.slot_id)
            name = constraint_name(constraint.constraint_type.constraint_name)
            index.by_faculty[constraint.faculty_id].append(constraint)

            if constraint.constraint_type.is_hard_constraint and name == "UNAVAILABLE":
                index.unavailable.add(key)
            elif name == "PREFERRED":
                index.preferred.add(key)
            elif name == "AVOID":
                index.avoid.add(key)

        return index

    def is_unavailable(self, faculty_id: int, day_id: int, slot_ids: tuple[int, ...]) -> bool:
        return any((faculty_id, day_id, slot_id) in self.unavailable for slot_id in slot_ids)

    def preferred_count(self, faculty_id: int, day_id: int, slot_ids: tuple[int, ...]) -> int:
        return sum((faculty_id, day_id, slot_id) in self.preferred for slot_id in slot_ids)

    def avoid_count(self, faculty_id: int, day_id: int, slot_ids: tuple[int, ...]) -> int:
        return sum((faculty_id, day_id, slot_id) in self.avoid for slot_id in slot_ids)
