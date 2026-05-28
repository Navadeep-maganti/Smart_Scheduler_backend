from django.db import models
from django.db.models.functions import Lower


class Building(models.Model):
    building_id = models.BigAutoField(primary_key=True)
    building_name = models.CharField(max_length=120, unique=True)

    class Meta:
        db_table = "building"

    def __str__(self):
        return self.building_name


class Room(models.Model):
    class RoomType(models.TextChoices):
        CLASSROOM = "CLASSROOM", "Classroom"
        COMPUTER_LAB = "COMPUTER_LAB", "Computer lab"
        HARDWARE_LAB = "HARDWARE_LAB", "Hardware lab"
        SEMINAR_HALL = "SEMINAR_HALL", "Seminar hall"

    room_id = models.BigAutoField(primary_key=True)
    room_name = models.CharField(max_length=80)
    room_type = models.CharField(max_length=20, choices=RoomType.choices)
    building = models.ForeignKey(Building, on_delete=models.PROTECT, related_name="rooms")
    capacity = models.PositiveIntegerField()
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rooms",
    )

    class Meta:
        db_table = "room"
        constraints = [
            models.UniqueConstraint(
                fields=["building", "room_name"],
                name="unique_room_name_per_building",
            )
        ]

    def __str__(self):
        return f"{self.building.building_name} / {self.room_name}"


class Day(models.Model):
    day_id = models.BigAutoField(primary_key=True)
    day_name = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = "day"
        constraints = [
            models.UniqueConstraint(
                Lower("day_name"),
                name="unique_day_name_case_insensitive",
            )
        ]

    def __str__(self):
        return self.day_name


class Timeslot(models.Model):
    slot_id = models.BigAutoField(primary_key=True)
    slot_number = models.PositiveSmallIntegerField(unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)

    class Meta:
        db_table = "timeslot"
        ordering = ["slot_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["start_time", "end_time"],
                name="unique_timeslot_time_range",
            )
        ]

    def __str__(self):
        return f"{self.slot_number}: {self.start_time}-{self.end_time}"
