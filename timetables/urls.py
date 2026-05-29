from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    GeneratePreviewView,
    GenerateTimetableView,
    RegenerateTimetableView,
    SessionGroupMemberViewSet,
    SessionGroupViewSet,
    TeachingAssignmentViewSet,
    TimetableEntryViewSet,
    TimetableViewSet,
)


router = DefaultRouter(trailing_slash="/?")
router.register("assignments", TeachingAssignmentViewSet, basename="teaching-assignment")
router.register("session-groups", SessionGroupViewSet, basename="session-group")
router.register("session-group-members", SessionGroupMemberViewSet, basename="session-group-member")
router.register("timetables", TimetableViewSet, basename="timetable")
router.register("entries", TimetableEntryViewSet, basename="timetable-entry")

urlpatterns = [
    path("generate-preview/", GeneratePreviewView.as_view(), name="timetable-generate-preview"),
    path("generate/", GenerateTimetableView.as_view(), name="timetable-generate"),
    path("regenerate/", RegenerateTimetableView.as_view(), name="timetable-regenerate"),
]

urlpatterns += router.urls
