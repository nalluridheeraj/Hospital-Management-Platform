import time
import uuid
from datetime import datetime
from django.db import connection, transaction, OperationalError, IntegrityError
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

from .models import Doctor, DoctorSlot, Patient, Appointment, AuditLog
from .serializers import (
    DoctorSerializer,
    DoctorSlotSerializer,
    PatientSerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentRescheduleSerializer,
    AuditLogSerializer,
)
from .permissions import IsAdminRole, IsDoctorOrAdmin

# Prometheus Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "django_hospital_http_requests_total",
    "Total count of HTTP requests",
    ["method", "endpoint", "status_code"],
)
APPOINTMENT_OPERATIONS = Counter(
    "django_hospital_appointment_operations_total",
    "Total appointment lifecycle operations",
    ["operation", "status"],
)


def log_audit_event(actor_id, actor_role, action, resource_type, resource_id=None, details=None, ip_address=None, status="SUCCESS"):
    """Records an immutable security audit entry."""
    try:
        AuditLog.objects.create(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            status=status,
        )
    except Exception as e:
        # Audit failures must not break request flow
        print(f"[AUDIT ERROR] {e}")


# -----------------------------------------------------------------------------
# 1. Observability: Health Probes & Metrics
# -----------------------------------------------------------------------------
class HealthLivenessView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            "status": "alive",
            "service": "Hospital Appointment Scheduling API",
            "version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
        })


class HealthReadinessView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        start_time = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return Response({
                "status": "ready",
                "service": "Hospital Appointment Scheduling API",
                "version": "1.0.0",
                "database": {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "database": "connected",
                },
                "timestamp": timezone.now().isoformat(),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return Response({
                "status": "unhealthy",
                "service": "Hospital Appointment Scheduling API",
                "version": "1.0.0",
                "database": {
                    "status": "disconnected",
                    "latency_ms": latency_ms,
                    "error": str(e),
                },
                "timestamp": timezone.now().isoformat(),
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class PrometheusMetricsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = generate_latest()
        return Response(data, content_type=CONTENT_TYPE_LATEST)


# -----------------------------------------------------------------------------
# 2. Doctors & Synthetic Patient Views
# -----------------------------------------------------------------------------
class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Doctor.objects.filter(is_active=True)
    serializer_class = DoctorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        specialty = self.request.query_params.get("specialization")
        if specialty:
            qs = qs.filter(specialization__icontains=specialty)
        return qs


class DoctorSlotListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, doctor_id):
        try:
            doctor = Doctor.objects.get(id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({"detail": f"Doctor '{doctor_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        available_only = request.query_params.get("available_only", "true").lower() in ("true", "1")
        slots = DoctorSlot.objects.filter(doctor=doctor)
        if available_only:
            slots = slots.filter(is_available=True)

        serializer = DoctorSlotSerializer(slots, many=True)
        return Response(serializer.data)


class PatientListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patients = Patient.objects.all()
        serializer = PatientSerializer(patients, many=True)
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# 3. Appointments ViewSet (Concurrency Protection & Slot Claim)
# -----------------------------------------------------------------------------
class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.all()

        # RBAC Data Isolation
        if not (user.is_staff or user.username == "admin"):
            if user.username.startswith("dr."):
                qs = qs.filter(doctor__email=user.email)
            else:
                qs = qs.filter(patient__email=user.email)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs

    def create(self, request, *args, **kwargs):
        client_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "unknown")
        )
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doctor = serializer.validated_data["doctor_obj"]
        patient = serializer.validated_data["patient_obj"]
        slot = serializer.validated_data["slot_obj"]

        # CONCURRENCY ATOMIC LOCK:
        # select_for_update() acquires a row-level write lock
        try:
            with transaction.atomic():
                locked_slot = (
                    DoctorSlot.objects.select_for_update()
                    .filter(id=slot.id, doctor=doctor, is_available=True)
                    .first()
                )

                if not locked_slot:
                    APPOINTMENT_OPERATIONS.labels(operation="book", status="conflict").inc()
                    log_audit_event(
                        actor_id=request.user.username,
                        actor_role="patient" if not request.user.is_staff else "admin",
                        action="APPOINTMENT_CONFLICT",
                        resource_type="appointment",
                        resource_id=slot.id,
                        details=f"Conflict: Doctor {doctor.name} slot {slot.id} already booked by concurrent request.",
                        ip_address=client_ip,
                        status="CONFLICT",
                    )
                    return Response(
                        {"detail": f"Conflict: Doctor {doctor.name} is already booked for this slot ({slot.start_time})."},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Slot claimed exclusively
                locked_slot.is_available = False
                locked_slot.save(update_fields=["is_available"])

                code_suffix = uuid.uuid4().hex[:6].upper()
                apt_code = f"APT-{locked_slot.start_time.strftime('%Y%m%d%H%M')}-{code_suffix}"

                appointment = Appointment.objects.create(
                    appointment_code=apt_code,
                    doctor=doctor,
                    patient=patient,
                    slot=locked_slot,
                    start_time=locked_slot.start_time,
                    end_time=locked_slot.end_time,
                    status=Appointment.STATUS_CONFIRMED,
                    reason=serializer.validated_data["reason"],
                    notes=serializer.validated_data.get("notes", ""),
                )
        except (OperationalError, IntegrityError):
            APPOINTMENT_OPERATIONS.labels(operation="book", status="conflict").inc()
            return Response(
                {"detail": f"Conflict: Doctor {doctor.name} slot is locked by another concurrent booking request."},
                status=status.HTTP_409_CONFLICT,
            )

        APPOINTMENT_OPERATIONS.labels(operation="book", status="success").inc()
        log_audit_event(
            actor_id=request.user.username,
            actor_role="patient" if not request.user.is_staff else "admin",
            action="APPOINTMENT_CREATED",
            resource_type="appointment",
            resource_id=appointment.id,
            details=f"Appointment {apt_code} booked with {doctor.name} for {locked_slot.start_time}",
            ip_address=client_ip,
            status="SUCCESS",
        )

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        client_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "unknown")
        )
        appointment = self.get_object()

        if appointment.status == Appointment.STATUS_CANCELLED:
            return Response(
                {"detail": "Cannot reschedule a cancelled appointment. Please book a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AppointmentRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_slot_id = serializer.validated_data["new_slot_id"]

        with transaction.atomic():
            new_slot = (
                DoctorSlot.objects.select_for_update()
                .filter(id=new_slot_id, doctor=appointment.doctor, is_available=True)
                .first()
            )

            if not new_slot:
                APPOINTMENT_OPERATIONS.labels(operation="reschedule", status="conflict").inc()
                return Response(
                    {"detail": "The requested new slot is unavailable or already booked."},
                    status=status.HTTP_409_CONFLICT,
                )

            if new_slot.start_time <= timezone.now():
                return Response(
                    {"detail": "Cannot reschedule to a slot in the past."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Free old slot
            old_slot = appointment.slot
            old_slot.is_available = True
            old_slot.save(update_fields=["is_available"])

            # Claim new slot
            new_slot.is_available = False
            new_slot.save(update_fields=["is_available"])

            # Update appointment
            appointment.slot = new_slot
            appointment.start_time = new_slot.start_time
            appointment.end_time = new_slot.end_time
            appointment.status = Appointment.STATUS_RESCHEDULED
            reschedule_reason = serializer.validated_data.get("reason", "")
            if reschedule_reason:
                appointment.notes = f"{appointment.notes or ''} [Rescheduled: {reschedule_reason}]"
            appointment.save()

        APPOINTMENT_OPERATIONS.labels(operation="reschedule", status="success").inc()
        log_audit_event(
            actor_id=request.user.username,
            actor_role="patient" if not request.user.is_staff else "admin",
            action="APPOINTMENT_RESCHEDULED",
            resource_type="appointment",
            resource_id=appointment.id,
            details=f"Appointment {appointment.appointment_code} rescheduled to {new_slot.start_time}",
            ip_address=client_ip,
            status="SUCCESS",
        )

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path="cancel")
    def cancel(self, request, pk=None):
        client_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "unknown")
        )
        appointment = self.get_object()

        if appointment.status == Appointment.STATUS_CANCELLED:
            return Response(
                {"detail": "Appointment is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            slot = appointment.slot
            slot.is_available = True
            slot.save(update_fields=["is_available"])

            appointment.status = Appointment.STATUS_CANCELLED
            appointment.save(update_fields=["status"])

        APPOINTMENT_OPERATIONS.labels(operation="cancel", status="success").inc()
        log_audit_event(
            actor_id=request.user.username,
            actor_role="patient" if not request.user.is_staff else "admin",
            action="APPOINTMENT_CANCELLED",
            resource_type="appointment",
            resource_id=appointment.id,
            details=f"Appointment {appointment.appointment_code} was cancelled.",
            ip_address=client_ip,
            status="SUCCESS",
        )

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# 4. Audit Trail View (Admin Only)
# -----------------------------------------------------------------------------
class AuditLogListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        logs = AuditLog.objects.all()
        action_filter = request.query_params.get("action")
        if action_filter:
            logs = logs.filter(action=action_filter)
        serializer = AuditLogSerializer(logs[:100], many=True)
        return Response(serializer.data)
