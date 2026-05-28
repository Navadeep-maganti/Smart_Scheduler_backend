from django.contrib import admin

from .models import (
    SessionGroup,
    SessionGroupMember,
    TeachingAssignment,
    Timetable,
    TimetableEntry,
)


admin.site.register(
    [
        SessionGroup,
        SessionGroupMember,
        TeachingAssignment,
        Timetable,
        TimetableEntry,
    ]
)
