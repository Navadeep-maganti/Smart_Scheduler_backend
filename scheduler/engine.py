from django.db import transaction
from django.db.models import Max

from scheduler.allocator import TimetableAllocator
from scheduler.generator import load_scheduler_data
from scheduler.models import GenerationResult
from scheduler.occupancy import OccupancyMap
from scheduler.prioritizer import prioritize_units
from timetables.models import Timetable, TimetableEntry


class SchedulerEngine:
    def generate(
        self,
        *,
        term_id: int,
        section_ids: list[int] | None = None,
        generated_by_id: int | None = None,
        locked_timetable_ids: list[int] | None = None,
        persist: bool = True,
    ) -> GenerationResult:
        data = load_scheduler_data(term_id=term_id, section_ids=section_ids)
        units = prioritize_units(data.units)
        occupancy = self.build_initial_occupancy(locked_timetable_ids or [], data.timeslots)

        allocator = TimetableAllocator(
            units=units,
            days=data.days,
            timeslots=data.timeslots,
            rooms=data.rooms,
            faculty_constraints=data.faculty_constraints,
            occupancy=occupancy,
        )
        result = allocator.allocate()

        if result.success and persist:
            self.persist(term_id=term_id, allocations=result.allocations, generated_by_id=generated_by_id)

        return result

    def build_initial_occupancy(self, timetable_ids: list[int], timeslots: list) -> OccupancyMap:
        occupancy = OccupancyMap()
        if not timetable_ids:
            return occupancy

        entries = TimetableEntry.objects.filter(
            timetable_id__in=timetable_ids,
            status=TimetableEntry.Status.SCHEDULED,
        ).select_related("assignment", "timetable")
        slot_id_by_number = {slot.slot_number: slot.slot_id for slot in timeslots}
        slot_number_by_id = {slot.slot_id: slot.slot_number for slot in timeslots}
        occupancy.load_timetable_entries(
            entries,
            slot_id_by_number=slot_id_by_number,
            slot_number_by_id=slot_number_by_id,
        )
        return occupancy

    @transaction.atomic
    def persist(self, *, term_id: int, allocations, generated_by_id: int | None = None):
        section_ids = sorted({allocation.session.section_id for allocation in allocations})
        timetable_by_section_id = {}

        for section_id in section_ids:
            latest_version = (
                Timetable.objects.filter(section_id=section_id, term_id=term_id)
                .aggregate(max_version=Max("version_number"))
                .get("max_version")
                or 0
            )
            timetable_by_section_id[section_id] = Timetable.objects.create(
                section_id=section_id,
                term_id=term_id,
                version_number=latest_version + 1,
                status=Timetable.Status.GENERATED,
                generated_by_id=generated_by_id,
            )

        entries = [
            TimetableEntry(
                timetable=timetable_by_section_id[allocation.session.section_id],
                assignment_id=allocation.session.assignment_id,
                day_id=allocation.day_id,
                starting_slot_id=allocation.starting_slot_id,
                duration=len(allocation.slot_ids),
                room_id=allocation.room_id,
                entry_type=TimetableEntry.EntryType.REGULAR,
                status=TimetableEntry.Status.SCHEDULED,
            )
            for allocation in allocations
        ]
        TimetableEntry.objects.bulk_create(entries)
