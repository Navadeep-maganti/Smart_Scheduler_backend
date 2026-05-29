from rest_framework.routers import DefaultRouter

from .views import BuildingViewSet, DayViewSet, RoomViewSet, TimeslotViewSet


router = DefaultRouter(trailing_slash="/?")
router.register("buildings", BuildingViewSet, basename="building")
router.register("rooms", RoomViewSet, basename="room")
router.register("days", DayViewSet, basename="day")
router.register("timeslots", TimeslotViewSet, basename="timeslot")

urlpatterns = router.urls
