from django.db import models
from django.core.exceptions import ValidationError


class AppUser(models.Model):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        FACULTY = "FACULTY", "Faculty"
        ADMIN = "ADMIN", "Admin"
        HOD = "HOD", "HOD"

    user_id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        db_table = "app_user"

    def __str__(self):
        return self.email


class Student(models.Model):
    student_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        AppUser,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    roll_no = models.CharField(max_length=30, unique=True)
    student_name = models.CharField(max_length=120)
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.PROTECT,
        related_name="students",
    )

    class Meta:
        db_table = "student"

    def clean(self):
        if self.user_id and self.user.role != AppUser.Role.STUDENT:
            raise ValidationError({"user": "Selected user must have the STUDENT role."})

    def __str__(self):
        return f"{self.roll_no} - {self.student_name}"


class Faculty(models.Model):
    user = models.OneToOneField(
        AppUser,
        on_delete=models.CASCADE,
        related_name="faculty_profile",
    )
    faculty_id = models.BigAutoField(primary_key=True)
    faculty_name = models.CharField(max_length=120)
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.PROTECT,
        related_name="faculty",
    )

    class Meta:
        db_table = "faculty"
        verbose_name_plural = "faculty"

    def clean(self):
        faculty_roles = {AppUser.Role.FACULTY, AppUser.Role.HOD}
        if self.user_id and self.user.role not in faculty_roles:
            raise ValidationError({"user": "Selected user must have the FACULTY or HOD role."})

    def __str__(self):
        return self.faculty_name
