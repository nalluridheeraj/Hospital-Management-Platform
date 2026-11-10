import pytest
from appointments.models import Doctor, DoctorSlot, Patient, AuditLog


@pytest.mark.django_db
def test_audit_log_tracking_and_admin_inspection(patient_client, admin_client):
    """Verify that clinical and security events are logged into the immutable audit trail
    and can be retrieved by an administrator.
    """
    # 1. Generate an audit event by making an appointment
    doctor = Doctor.objects.all()[3]
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()
    patient = Patient.objects.all()[3]

    create_resp = patient_client.post(
        "/api/v1/appointments/",
        {
            "doctor_id": doctor.id,
            "slot_id": slot.id,
            "patient_id": patient.id,
            "reason": "Orthopedic assessment",
        },
        format="json",
    )
    assert create_resp.status_code == 201

    # 2. Fetch audit logs as admin
    audit_resp = admin_client.get("/api/v1/audit-logs/")
    assert audit_resp.status_code == 200
    logs = audit_resp.data
    assert len(logs) > 0

    actions = [log["action"] for log in logs]
    assert "APPOINTMENT_CREATED" in actions
