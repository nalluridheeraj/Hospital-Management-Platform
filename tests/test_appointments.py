import pytest
from datetime import timedelta
from django.utils import timezone
from appointments.models import Doctor, DoctorSlot, Patient, Appointment


@pytest.mark.django_db
def test_list_doctors(patient_client):
    """Verify listing active seeded doctors."""
    response = patient_client.get("/api/v1/doctors/")
    assert response.status_code == 200
    doctors = response.data
    assert len(doctors) >= 4
    names = [d["name"] for d in doctors]
    assert "Dr. Alice Smith" in names


@pytest.mark.django_db
def test_list_doctor_slots(patient_client):
    """Verify listing available slots for a specific doctor."""
    doctor = Doctor.objects.first()
    response = patient_client.get(f"/api/v1/doctors/{doctor.id}/slots/")
    assert response.status_code == 200
    slots = response.data
    assert len(slots) > 0
    assert all(s["is_available"] is True for s in slots)


@pytest.mark.django_db
def test_book_appointment_success(patient_client):
    """Verify normal appointment creation workflow with synthetic patient data."""
    doctor = Doctor.objects.first()
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()
    patient = Patient.objects.first()

    payload = {
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "patient_id": patient.id,
        "reason": "Cardiology evaluation",
        "notes": "Synthetic patient checkup notes.",
    }

    response = patient_client.post("/api/v1/appointments/", payload, format="json")
    assert response.status_code == 201
    data = response.data
    assert data["status"] == "CONFIRMED"
    assert data["doctor_id"] == doctor.id
    assert data["slot_id"] == slot.id
    assert "appointment_code" in data

    # Slot must now be marked unavailable
    slot.refresh_from_db()
    assert slot.is_available is False


@pytest.mark.django_db
def test_book_appointment_invalid_doctor(patient_client):
    """Verify validation rejection when doctor does not exist."""
    patient = Patient.objects.first()
    slot = DoctorSlot.objects.first()

    payload = {
        "doctor_id": "non-existent-doctor-id",
        "slot_id": slot.id,
        "patient_id": patient.id,
        "reason": "Checkup",
    }

    response = patient_client.post("/api/v1/appointments/", payload, format="json")
    assert response.status_code == 400
    assert "doctor_id" in response.data


@pytest.mark.django_db
def test_book_appointment_invalid_patient(patient_client):
    """Verify validation rejection when patient does not exist."""
    doctor = Doctor.objects.first()
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()

    payload = {
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "patient_id": "non-existent-patient-id",
        "reason": "Checkup",
    }

    response = patient_client.post("/api/v1/appointments/", payload, format="json")
    assert response.status_code == 400
    assert "patient_id" in response.data


@pytest.mark.django_db
def test_reschedule_appointment(patient_client):
    """Verify appointment rescheduling transfers slot availability cleanly."""
    doctor = Doctor.objects.all()[1]
    slots = list(DoctorSlot.objects.filter(doctor=doctor, is_available=True)[:2])
    slot_1 = slots[0]
    slot_2 = slots[1]
    patient = Patient.objects.first()

    # 1. Book first slot
    book_resp = patient_client.post(
        "/api/v1/appointments/",
        {
            "doctor_id": doctor.id,
            "slot_id": slot_1.id,
            "patient_id": patient.id,
            "reason": "Initial consult",
        },
        format="json",
    )
    assert book_resp.status_code == 201
    apt_id = book_resp.data["id"]

    # 2. Reschedule to second slot
    resched_resp = patient_client.put(
        f"/api/v1/appointments/{apt_id}/reschedule/",
        {"new_slot_id": slot_2.id, "reason": "Patient requested evening schedule"},
        format="json",
    )
    assert resched_resp.status_code == 200
    assert resched_resp.data["status"] == "RESCHEDULED"
    assert resched_resp.data["slot_id"] == slot_2.id

    # Verify old slot is available again, new slot is booked
    slot_1.refresh_from_db()
    slot_2.refresh_from_db()
    assert slot_1.is_available is True
    assert slot_2.is_available is False


@pytest.mark.django_db
def test_cancel_appointment(patient_client):
    """Verify cancelling appointment restores doctor slot availability."""
    doctor = Doctor.objects.all()[2]
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()
    patient = Patient.objects.first()

    book_resp = patient_client.post(
        "/api/v1/appointments/",
        {
            "doctor_id": doctor.id,
            "slot_id": slot.id,
            "patient_id": patient.id,
            "reason": "Pediatric consultation",
        },
        format="json",
    )
    assert book_resp.status_code == 201
    apt_id = book_resp.data["id"]

    # Cancel
    cancel_resp = patient_client.delete(f"/api/v1/appointments/{apt_id}/cancel/")
    assert cancel_resp.status_code == 200
    assert cancel_resp.data["status"] == "CANCELLED"

    slot.refresh_from_db()
    assert slot.is_available is True
