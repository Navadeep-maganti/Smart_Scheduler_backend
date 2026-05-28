from django.core.management.base import BaseCommand, CommandError

from timetables.models import Timetable, TimetableEntry


class Command(BaseCommand):
    help = "Print a generated timetable for a section."

    def add_arguments(self, parser):
        parser.add_argument("--section-id", type=int, required=True)
        parser.add_argument("--term-id", type=int, required=True)
        parser.add_argument("--timetable-version", type=int, default=None)

    def handle(self, *args, **options):
        timetable_query = Timetable.objects.filter(
            section_id=options["section_id"],
            term_id=options["term_id"],
        )
        if options["timetable_version"]:
            timetable_query = timetable_query.filter(version_number=options["timetable_version"])
        else:
            timetable_query = timetable_query.order_by("-version_number")

        timetable = timetable_query.first()
        if not timetable:
            raise CommandError("No timetable found for the supplied section/term.")

        entries = (
            TimetableEntry.objects.filter(timetable=timetable)
            .select_related(
                "assignment__subject",
                "assignment__faculty",
                "day",
                "starting_slot",
                "room__building",
            )
            .order_by("day__day_id", "starting_slot__slot_number", "assignment__subject_id")
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{timetable.section} | term={timetable.term_id} | version={timetable.version_number} | status={timetable.status}"
            )
        )
        for entry in entries:
            self.stdout.write(
                f"{entry.day.day_name:<10} "
                f"S{entry.starting_slot.slot_number:<2} "
                f"dur={entry.duration:<1} "
                f"{entry.assignment.subject.subject_code:<6} "
                f"{entry.assignment.subject.subject_title:<38} "
                f"{entry.assignment.faculty.faculty_name:<24} "
                f"{entry.room.room_name}"
            )
