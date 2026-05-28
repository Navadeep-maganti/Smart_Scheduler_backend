from django.db import models


class ConstraintType(models.Model):
    constraint_type_id = models.BigAutoField(primary_key=True)
    constraint_name = models.CharField(max_length=120, unique=True)
    constraint_category = models.CharField(max_length=80)
    priority_level = models.PositiveSmallIntegerField(default=3)
    is_hard_constraint = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "constraint_type"

    def __str__(self):
        return self.constraint_name


class FacultyConstraint(models.Model):
    constraint_id = models.BigAutoField(primary_key=True)
    faculty = models.ForeignKey(
        "accounts.Faculty",
        on_delete=models.CASCADE,
        related_name="constraints",
    )
    day = models.ForeignKey(
        "infrastructure.Day",
        on_delete=models.CASCADE,
        related_name="faculty_constraints",
    )
    slot = models.ForeignKey(
        "infrastructure.Timeslot",
        on_delete=models.CASCADE,
        related_name="faculty_constraints",
    )
    constraint_type = models.ForeignKey(
        ConstraintType,
        on_delete=models.PROTECT,
        related_name="faculty_constraints",
    )
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = "faculty_constraint"
        constraints = [
            models.UniqueConstraint(
                fields=["faculty", "day", "slot", "constraint_type"],
                name="unique_faculty_constraint",
            )
        ]

    def __str__(self):
        return f"{self.faculty} - {self.day} - {self.slot}"
