from rest_framework.routers import DefaultRouter

from .views import ConstraintTypeViewSet, FacultyConstraintViewSet


router = DefaultRouter(trailing_slash="/?")
router.register("types", ConstraintTypeViewSet, basename="constraint-type")
router.register("faculty", FacultyConstraintViewSet, basename="faculty-constraint")

urlpatterns = router.urls
