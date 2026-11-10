from rest_framework import serializers
from django.utils import timezone
from .models import Doctor, DoctorSlot, Patient, Appointment, AuditLog


class DoctorSlotSerializer(serializers.ModelSerializer):
    doctor_id = serializers.CharField(source="doctor.id", read_only=True)

    class Meta:
        model = DoctorSlot
        fields = ["id", "doctor_id", "start_time", "end_time", "is_available"]


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["id", "doctor_code", "name", "specialization", "department", "email", "is_active"]


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["id", "patient_code", "full_name", "date_of_birth", "phone", "email"]


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_id = serializers.CharField(source="doctor.id", read_only=True)
    doctor_name = serializers.CharField(source="doctor.name", read_only=True)
    patient_id = serializers.CharField(source="patient.id", read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    slot_id = serializers.CharField(source="slot.id", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "appointment_code",
            "doctor_id",
            "doctor_name",
            "patient_id",
            "patient_name",
            "slot_id",
            "start_time",
            "end_time",
            "status",
            "reason",
            "notes",
            "created_at",
            "updated_at",
        ]


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.CharField(required=True)
    slot_id = serializers.CharField(required=True)
    patient_id = serializers.CharField(required=True)
    reason = serializers.CharField(required=True, min_length=3, max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        # 1. Validate Doctor
        try:
            doctor = Doctor.objects.get(id=attrs["doctor_id"], is_active=True)
        except Doctor.DoesNotExist:
            raise serializers.ValidationError({"doctor_id": "Doctor does not exist or is inactive."})

        # 2. Validate Patient
        try:
            patient = Patient.objects.get(id=attrs["patient_id"])
        except Patient.DoesNotExist:
            raise serializers.ValidationError({"patient_id": "Patient does not exist."})

        # 3. Validate Slot
        try:
            slot = DoctorSlot.objects.get(id=attrs["slot_id"], doctor=doctor)
        except DoctorSlot.DoesNotExist:
            raise serializers.ValidationError({"slot_id": "Slot does not exist or does not belong to the selected doctor."})

        # 4. Validate Future Window
        if slot.start_time <= timezone.now():
            raise serializers.ValidationError({"slot_id": "Cannot book an appointment for an expired or past time slot."})

        attrs["doctor_obj"] = doctor
        attrs["patient_obj"] = patient
        attrs["slot_obj"] = slot
        return attrs


class AppointmentRescheduleSerializer(serializers.Serializer):
    new_slot_id = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "actor_id",
            "actor_role",
            "action",
            "resource_type",
            "resource_id",
            "details",
            "ip_address",
            "status",
        ]

