from django.contrib import admin

from .models import ConstraintType, FacultyConstraint


admin.site.register([ConstraintType, FacultyConstraint])
