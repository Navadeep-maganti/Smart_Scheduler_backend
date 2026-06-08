from django.core.exceptions import ValidationError
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class AppUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The email field must be set.")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("role", AppUser.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class AppUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        FACULTY = "FACULTY", "Faculty"
        ADMIN = "ADMIN", "Admin"
        HOD = "HOD", "HOD"

    ROLE_PERMISSIONS = {
        Role.STUDENT: {
            "profile:read_self",
            "password:change_self",
        },
        Role.FACULTY: {
            "profile:read_self",
            "password:change_self",
            "timetable:read_assigned",
            "constraints:read_self",
            "constraints:write_self",
        },
        Role.HOD: {
            "profile:read_self",
            "password:change_self",
            "timetable:read_assigned",
            "timetable:read_department",
            "timetable:write_department",
            "constraints:read_self",
            "constraints:write_self",
            "constraints:read_department",
            "constraints:write_department",
            "department:read",
            "faculty:read",
            "infrastructure:read",
            "timetable:review_department",
        },
        Role.ADMIN: {
            "profile:read_self",
            "password:change_self",
            "auth:manage_roles",
            "users:read",
            "users:write",
            "department:read",
            "department:write",
            "faculty:read",
            "faculty:write",
            "infrastructure:read",
            "infrastructure:write",
            "students:read",
            "students:write",
            "timetable:read",
            "timetable:write",
            "constraints:read",
            "constraints:write",
        },
    }

    user_id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = AppUserManager()

    class Meta:
        db_table = "app_user"

    def __str__(self):
        return self.email

    @property
    def permissions(self):
        return sorted(self.ROLE_PERMISSIONS.get(self.role, set()))

    def has_role(self, *roles):
        return self.role in set(roles)

    def has_permission_code(self, permission_code):
        return permission_code in self.ROLE_PERMISSIONS.get(self.role, set())


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
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="students",
    )

    class Meta:
        db_table = "student"

    def clean(self):
        if self.user_id and self.user.role != AppUser.Role.STUDENT:
            raise ValidationError({"user": "Selected user must have the STUDENT role."})
        if self.section_id and self.department_id and self.section.department_id != self.department_id:
            raise ValidationError({"section": "Selected section must belong to the student's department."})

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
