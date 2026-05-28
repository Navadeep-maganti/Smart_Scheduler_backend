from django.contrib import admin

from .models import AcademicTerm, Department, Section, Subject


admin.site.register([AcademicTerm, Department, Section, Subject])
