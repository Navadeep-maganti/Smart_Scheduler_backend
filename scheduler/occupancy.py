from scheduler.models import SessionAllocation


class OccupancyMap:
    def __init__(self):
        self.faculty_busy: set[tuple[int, int, int]] = set()
        self.room_busy: set[tuple[int, int, int]] = set()
        self.section_busy: set[tuple[int, int, int]] = set()
        self.section_day_load: dict[tuple[int, int], int] = {}

    def is_faculty_free(self, faculty_id: int, day_id: int, slot_ids: tuple[int, ...]) -> bool:
        return all((faculty_id, day_id, slot_id) not in self.faculty_busy for slot_id in slot_ids)

    def is_room_free(self, room_id: int, day_id: int, slot_ids: tuple[int, ...]) -> bool:
        return all((room_id, day_id, slot_id) not in self.room_busy for slot_id in slot_ids)

    def is_section_free(self, section_id: int, day_id: int, slot_ids: tuple[int, ...]) -> bool:
        return all((section_id, day_id, slot_id) not in self.section_busy for slot_id in slot_ids)

    def can_place(
        self,
        faculty_id: int,
        section_id: int,
        room_id: int,
        day_id: int,
        slot_ids: tuple[int, ...],
    ) -> bool:
        return (
            self.is_faculty_free(faculty_id, day_id, slot_ids)
            and self.is_section_free(section_id, day_id, slot_ids)
            and self.is_room_free(room_id, day_id, slot_ids)
        )

    def occupy(self, allocation: SessionAllocation):
        for slot_id in allocation.slot_ids:
            self.faculty_busy.add((allocation.session.faculty_id, allocation.day_id, slot_id))
            self.section_busy.add((allocation.session.section_id, allocation.day_id, slot_id))
            self.room_busy.add((allocation.room_id, allocation.day_id, slot_id))

        key = (allocation.session.section_id, allocation.day_id)
        self.section_day_load[key] = self.section_day_load.get(key, 0) + len(allocation.slot_ids)

    def release(self, allocation: SessionAllocation):
        for slot_id in allocation.slot_ids:
            self.faculty_busy.discard((allocation.session.faculty_id, allocation.day_id, slot_id))
            self.section_busy.discard((allocation.session.section_id, allocation.day_id, slot_id))
            self.room_busy.discard((allocation.room_id, allocation.day_id, slot_id))

        key = (allocation.session.section_id, allocation.day_id)
        self.section_day_load[key] = max(0, self.section_day_load.get(key, 0) - len(allocation.slot_ids))

    def load_timetable_entries(self, entries, *, slot_id_by_number: dict[int, int], slot_number_by_id: dict[int, int]):
        for entry in entries:
            start_number = slot_number_by_id[entry.starting_slot_id]
            slot_ids = tuple(
                slot_id_by_number[start_number + offset]
                for offset in range(entry.duration)
                if start_number + offset in slot_id_by_number
            )

            for slot_id in slot_ids:
                self.faculty_busy.add((entry.assignment.faculty_id, entry.day_id, slot_id))
                self.section_busy.add((entry.timetable.section_id, entry.day_id, slot_id))
                self.room_busy.add((entry.room_id, entry.day_id, slot_id))

            key = (entry.timetable.section_id, entry.day_id)
            self.section_day_load[key] = self.section_day_load.get(key, 0) + len(slot_ids)
