from django.db import models
from django.core.exceptions import ValidationError


class Department(models.Model):
    department_id = models.BigAutoField(primary_key=True)
    department_code = models.CharField(max_length=20, unique=True)
    department_name = models.CharField(max_length=120, unique=True)
    hod = models.ForeignKey(
        "accounts.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )

    class Meta:
        db_table = "department"
        constraints = [
            models.UniqueConstraint(
                fields=["hod"],
                condition=models.Q(hod__isnull=False),
                name="unique_department_hod",
            )
        ]

    def clean(self):
        if self.hod_id and self.hod.department_id != self.department_id:
            raise ValidationError({"hod": "HOD must belong to this department."})

    def __str__(self):
        return self.department_code


class AcademicTerm(models.Model):
    class TermType(models.TextChoices):
        ODD = "ODD", "Odd"
        EVEN = "EVEN", "Even"

    term_id = models.BigAutoField(primary_key=True)
    academic_year = models.CharField(max_length=9)
    term_type = models.CharField(max_length=10, choices=TermType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "academic_term"
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "term_type"],
                name="unique_academic_year_term_type",
            )
        ]

    def __str__(self):
        return f"{self.academic_year} {self.get_term_type_display()}"


class Section(models.Model):
    section_id = models.BigAutoField(primary_key=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="sections")
    academic_term = models.ForeignKey(AcademicTerm, on_delete=models.PROTECT, related_name="sections")
    year_number = models.PositiveSmallIntegerField()
    section_name = models.CharField(max_length=20)
    student_strength = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "section"
        constraints = [
            models.UniqueConstraint(
                fields=["department", "academic_term", "year_number", "section_name"],
                name="unique_section_per_term",
            )
        ]

    def __str__(self):
        return f"{self.department.department_code}-{self.year_number}{self.section_name}"


class Subject(models.Model):
    class SubjectType(models.TextChoices):
        THEORY = "THEORY", "Theory"
        LAB = "LAB", "Lab"
        SEMINAR = "SEMINAR", "Seminar"

    class RequiredRoomType(models.TextChoices):
        CLASSROOM = "CLASSROOM", "Classroom"
        COMPUTER_LAB = "COMPUTER_LAB", "Computer lab"
        HARDWARE_LAB = "HARDWARE_LAB", "Hardware lab"
        SEMINAR_HALL = "SEMINAR_HALL", "Seminar hall"

    subject_code = models.CharField(max_length=30, primary_key=True)
    subject_title = models.CharField(max_length=160)
    credits = models.PositiveSmallIntegerField()
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="subjects")
    subject_type = models.CharField(max_length=20, choices=SubjectType.choices, default=SubjectType.THEORY)
    sessions_per_week = models.PositiveSmallIntegerField(default=3)
    session_duration = models.PositiveSmallIntegerField(default=1)
    required_room_type = models.CharField(
        max_length=30,
        choices=RequiredRoomType.choices,
        default=RequiredRoomType.CLASSROOM,
    )

    class Meta:
        db_table = "subject"

    def __str__(self):
        return f"{self.subject_code} - {self.subject_title}"
