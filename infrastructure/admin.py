from django.contrib import admin

from .models import Building, Day, Room, Timeslot


admin.site.register([Building, Day, Room, Timeslot])
