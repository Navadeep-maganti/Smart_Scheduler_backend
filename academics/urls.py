from rest_framework.routers import DefaultRouter

from .views import AcademicTermViewSet, DepartmentViewSet, SectionViewSet, SubjectViewSet


router = DefaultRouter(trailing_slash="/?")
router.register("departments", DepartmentViewSet, basename="department")
router.register("terms", AcademicTermViewSet, basename="academic-term")
router.register("sections", SectionViewSet, basename="section")
router.register("subjects", SubjectViewSet, basename="subject")

urlpatterns = router.urls
