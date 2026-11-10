from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DoctorViewSet,
    DoctorSlotListView,
    PatientListView,
    AppointmentViewSet,
    AuditLogListView,
)

router = DefaultRouter()
router.register(r"doctors", DoctorViewSet, basename="doctor")
router.register(r"appointments", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("", include(router.urls)),
    path("doctors/<str:doctor_id>/slots/", DoctorSlotListView.as_view(), name="doctor-slots"),
    path("patients/", PatientListView.as_view(), name="patients"),
    path("audit-logs/", AuditLogListView.as_view(), name="audit-logs"),
]

