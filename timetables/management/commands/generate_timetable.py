from django.core.management.base import BaseCommand, CommandError

from academics.models import AcademicTerm
from scheduler.engine import SchedulerEngine


class Command(BaseCommand):
    help = "Generate a semester timetable using the heuristic scheduler engine."

    def add_arguments(self, parser):
        parser.add_argument("--term-id", type=int, help="Academic term id to generate for.")
        parser.add_argument(
            "--section-id",
            type=int,
            action="append",
            dest="section_ids",
            help="Optional section id. Pass multiple times for multiple sections.",
        )
        parser.add_argument("--generated-by-id", type=int, default=None)
        parser.add_argument(
            "--lock-timetable-id",
            type=int,
            action="append",
            dest="locked_timetable_ids",
            help="Existing timetable id whose scheduled entries should be treated as fixed occupancy.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        term_id = options["term_id"]
        if not term_id:
            active_term = AcademicTerm.objects.filter(is_active=True).order_by("-start_date").first()
            if not active_term:
                raise CommandError("No --term-id supplied and no active academic term exists.")
            term_id = active_term.term_id

        result = SchedulerEngine().generate(
            term_id=term_id,
            section_ids=options["section_ids"],
            generated_by_id=options["generated_by_id"],
            locked_timetable_ids=options["locked_timetable_ids"],
            persist=not options["dry_run"],
        )

        if not result.success:
            self.stderr.write(self.style.ERROR(result.message))
            raise CommandError("Timetable generation failed.")

        mode = "dry-run" if options["dry_run"] else "persisted"
        self.stdout.write(
            self.style.SUCCESS(
                f"Timetable generation {mode}: {len(result.allocations)} entries. {result.message}"
            )
        )
