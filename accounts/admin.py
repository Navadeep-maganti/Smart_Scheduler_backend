from django.contrib import admin

from .models import AppUser, Faculty, Student


admin.site.register([AppUser, Faculty, Student])
