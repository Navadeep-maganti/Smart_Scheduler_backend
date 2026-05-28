from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class TeachingAssignment(models.Model):
    class RequiredRoomType(models.TextChoices):
        CLASSROOM = "CLASSROOM", "Classroom"
        COMPUTER_LAB = "COMPUTER_LAB", "Computer lab"
        HARDWARE_LAB = "HARDWARE_LAB", "Hardware lab"
        SEMINAR_HALL = "SEMINAR_HALL", "Seminar hall"
        ANY = "ANY", "Any"

    assignment_id = models.BigAutoField(primary_key=True)
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        related_name="teaching_assignments",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    faculty = models.ForeignKey(
        "accounts.Faculty",
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    required_room_type = models.CharField(
        max_length=20,
        choices=RequiredRoomType.choices,
        default=RequiredRoomType.CLASSROOM,
    )
    preferred_room = models.ForeignKey(
        "infrastructure.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_assignments",
    )
    priority_level = models.PositiveSmallIntegerField(default=3)

    class Meta:
        db_table = "teaching_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["section", "subject", "faculty"],
                name="unique_teaching_assignment",
            )
        ]

    def clean(self):
        if self.preferred_room_id and self.required_room_type != self.RequiredRoomType.ANY:
            room_type_matches = self.preferred_room.room_type == self.required_room_type
            if not room_type_matches:
                raise ValidationError(
                    {"preferred_room": "Preferred room type must match the required room type."}
                )

    def __str__(self):
        return f"{self.section} - {self.subject_id} - {self.faculty}"


class SessionGroup(models.Model):
    class GroupCategory(models.TextChoices):
        PARALLEL_LAB = "PARALLEL_LAB", "Parallel lab"
        COMMON_ELECTIVE = "COMMON_ELECTIVE", "Common elective"

    group_id = models.BigAutoField(primary_key=True)
    group_name = models.CharField(max_length=120, unique=True)
    group_category = models.CharField(
        max_length=30,
        choices=GroupCategory.choices,
        default=GroupCategory.PARALLEL_LAB,
    )
    same_time_required = models.BooleanField(default=True)
    same_building_required = models.BooleanField(default=False)
    preferred_building = models.ForeignKey(
        "infrastructure.Building",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_session_groups",
    )
    priority_level = models.PositiveSmallIntegerField(default=3)

    class Meta:
        db_table = "session_group"

    def __str__(self):
        return self.group_name


class SessionGroupMember(models.Model):
    group_member_id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(SessionGroup, on_delete=models.CASCADE, related_name="members")
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE, related_name="session_groups")

    class Meta:
        db_table = "session_group_member"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "assignment"],
                name="unique_session_group_member",
            )
        ]

    def __str__(self):
        return f"{self.group} / {self.assignment}"


class Timetable(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        GENERATED = "GENERATED", "Generated"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    timetable_id = models.BigAutoField(primary_key=True)
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        related_name="timetables",
    )
    term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.PROTECT,
        related_name="timetables",
    )
    version_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(
        "accounts.AppUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_timetables",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "timetable"
        constraints = [
            models.UniqueConstraint(
                fields=["section", "term", "version_number"],
                name="unique_timetable_version",
            ),
            models.UniqueConstraint(
                fields=["section", "term"],
                condition=models.Q(status="PUBLISHED"),
                name="unique_published_timetable_per_section_term",
            ),
        ]

    def clean(self):
        if self.section_id and self.term_id and self.section.academic_term_id != self.term_id:
            raise ValidationError({"term": "Timetable term must match the section academic term."})

    def __str__(self):
        return f"{self.section} v{self.version_number}"


class TimetableEntry(models.Model):
    class EntryType(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        SUBSTITUTE = "SUBSTITUTE", "Substitute"
        EXTRA_CLASS = "EXTRA_CLASS", "Extra class"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        CANCELLED = "CANCELLED", "Cancelled"
        MODIFIED = "MODIFIED", "Modified"

    entry_id = models.BigAutoField(primary_key=True)
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name="entries")
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.PROTECT, related_name="timetable_entries")
    day = models.ForeignKey(
        "infrastructure.Day",
        on_delete=models.PROTECT,
        related_name="timetable_entries",
    )
    starting_slot = models.ForeignKey(
        "infrastructure.Timeslot",
        on_delete=models.PROTECT,
        related_name="starting_entries",
    )
    duration = models.PositiveSmallIntegerField(default=1)
    room = models.ForeignKey(
        "infrastructure.Room",
        on_delete=models.PROTECT,
        related_name="timetable_entries",
    )
    entry_type = models.CharField(max_length=20, choices=EntryType.choices, default=EntryType.REGULAR)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "timetable_entry"
        verbose_name_plural = "timetable entries"
        constraints = [
            models.UniqueConstraint(
                fields=["timetable", "day", "starting_slot", "assignment"],
                name="unique_assignment_slot_per_timetable",
            ),
            models.UniqueConstraint(
                fields=["timetable", "day", "starting_slot"],
                condition=models.Q(status="SCHEDULED"),
                name="unique_scheduled_section_slot",
            ),
            models.UniqueConstraint(
                fields=["timetable", "day", "starting_slot", "room"],
                condition=models.Q(status="SCHEDULED"),
                name="unique_scheduled_room_slot_per_timetable",
            ),
            models.UniqueConstraint(
                fields=["timetable", "day", "starting_slot", "assignment"],
                condition=models.Q(status="SCHEDULED"),
                name="unique_scheduled_assignment_slot_per_timetable",
            ),
        ]

    def clean(self):
        errors = {}

        if self.assignment_id and self.timetable_id:
            if self.assignment.section_id != self.timetable.section_id:
                errors["assignment"] = "Assignment must belong to the timetable section."

        if self.room_id and self.assignment_id:
            required_room_type = self.assignment.required_room_type
            room_type_matches = self.room.room_type == required_room_type
            if required_room_type != TeachingAssignment.RequiredRoomType.ANY and not room_type_matches:
                errors["room"] = "Room type must match the assignment required room type."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.timetable} - {self.day} slot {self.starting_slot_id}"
