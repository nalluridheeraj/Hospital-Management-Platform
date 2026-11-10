import uuid
from django.db import models
from django.utils import timezone


def generate_uuid_str():
    return str(uuid.uuid4())


class Doctor(models.Model):
    """Registered physicians with assigned clinical specialties."""

    id = models.CharField(primary_key=True, default=generate_uuid_str, max_length=36, editable=False)
    doctor_code = models.CharField(max_length=20, unique=True, db_index=True)  # e.g., DOC-001
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["doctor_code"]

    def __str__(self):
        return f"{self.doctor_code} - {self.name} ({self.specialization})"


class DoctorSlot(models.Model):
    """Scheduled consultation time windows for doctors."""

    id = models.CharField(primary_key=True, default=generate_uuid_str, max_length=36, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="slots")
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("doctor", "start_time")
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.doctor.name} @ {self.start_time.strftime('%Y-%m-%d %H:%M')} (Available: {self.is_available})"


class Patient(models.Model):
    """Synthetic patient profiles (strictly no real patient data)."""

    id = models.CharField(primary_key=True, default=generate_uuid_str, max_length=36, editable=False)
    patient_code = models.CharField(max_length=20, unique=True, db_index=True)  # e.g., PAT-001
    full_name = models.CharField(max_length=100)
    date_of_birth = models.CharField(max_length=10)  # YYYY-MM-DD
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["patient_code"]

    def __str__(self):
        return f"{self.patient_code} - {self.full_name}"


class Appointment(models.Model):
    """Doctor appointments with status tracking and slot binding."""

    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_RESCHEDULED = "RESCHEDULED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = (
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_RESCHEDULED, "Rescheduled"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    id = models.CharField(primary_key=True, default=generate_uuid_str, max_length=36, editable=False)
    appointment_code = models.CharField(max_length=50, unique=True, db_index=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="appointments")
    slot = models.ForeignKey(DoctorSlot, on_delete=models.PROTECT, related_name="appointments")
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED, db_index=True)
    reason = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.appointment_code} - {self.doctor.name} / {self.patient.full_name} [{self.status}]"


class AuditLog(models.Model):
    """Immutable audit trail for security and clinical governance."""

    id = models.CharField(primary_key=True, default=generate_uuid_str, max_length=36, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_id = models.CharField(max_length=50, db_index=True)
    actor_role = models.CharField(max_length=20)
    action = models.CharField(max_length=50, db_index=True)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=50, blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default="SUCCESS")

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.timestamp}] {self.actor_id} ({self.actor_role}): {self.action} -> {self.status}"
