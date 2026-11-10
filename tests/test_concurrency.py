import concurrent.futures
import pytest
from django.db import connection
from rest_framework.test import APIClient
from appointments.models import Doctor, DoctorSlot, Patient, Appointment


@pytest.mark.django_db(transaction=True)
def test_concurrent_conflicting_appointment_requests():
    """Acceptance Test: Demonstrates that under high-concurrency race conditions,
    two conflicting appointment requests for the same doctor and time slot
    can never both succeed. Exactly one must succeed (201), and all competing
    requests must be rejected with HTTP 409 Conflict.
    """
    from django.core.management import call_command
    call_command("seed_data", force=True)

    doctor = Doctor.objects.get(doctor_code="DOC-004")
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()
    assert slot is not None, "DOC-004 must have an available slot"
    patients = list(Patient.objects.all())
    assert len(patients) >= 2, "At least two synthetic patients required"

    # Pre-obtain JWT token for patient
    auth_client = APIClient()
    token_resp = auth_client.post(
        "/api/v1/auth/token/",
        {"username": "patient.john", "password": "Patient@Password2026!"},
        format="json",
    )
    assert token_resp.status_code == 200
    token = token_resp.data["access"]

    num_competing_requests = 10
    payload = {
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "patient_id": patients[0].id,
        "reason": "Concurrent race condition test booking",
    }

    def dispatch_booking(worker_idx: int):
        # Ensure fresh DB connection for each concurrent thread
        connection.close()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        worker_payload = payload.copy()
        worker_payload["patient_id"] = patients[worker_idx % len(patients)].id
        worker_payload["notes"] = f"Worker thread {worker_idx}"

        resp = client.post("/api/v1/appointments/", worker_payload, format="json")
        return resp.status_code, resp.data

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_competing_requests) as executor:
        futures = [executor.submit(dispatch_booking, i) for i in range(num_competing_requests)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    status_codes = [status for status, _ in results]
    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    print(f"\n[CONCURRENCY TEST RESULT] Success (201): {success_count}, Conflict (409): {conflict_count}")

    # Core Acceptance Assertion: Exactly ONE succeeds, ALL others receive 409 Conflict
    assert success_count == 1, (
        f"Expected exactly 1 successful booking under concurrency, but got {success_count}. "
        f"Statuses: {status_codes}"
    )
    assert conflict_count == num_competing_requests - 1, (
        f"Expected {num_competing_requests - 1} conflicts (409), but got {conflict_count}. "
        f"Statuses: {status_codes}"
    )

    # Database Verification: Exactly one appointment row exists for this slot
    appointments = Appointment.objects.filter(slot_id=slot.id)
    assert appointments.count() == 1, f"Expected 1 appointment row, found {appointments.count()}"

    slot.refresh_from_db()
    assert slot.is_available is False, "Doctor slot must be marked unavailable"
