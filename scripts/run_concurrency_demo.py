"""Live Concurrency Demonstration Script for Assessment Video / Reviewer.
Spawns 10 concurrent threads attempting to book the exact same doctor and time slot.
Verifies that exactly ONE request succeeds (201 Created) and ALL remaining requests
are rejected with HTTP 409 Conflict.
"""

import os
import sys
import concurrent.futures

# Setup Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.db import connection
from rest_framework.test import APIClient
from appointments.models import Doctor, DoctorSlot, Patient, Appointment


def run_concurrency_demonstration():
    print("=" * 70)
    print(" HOSPITAL MANAGEMENT PLATFORM - CONCURRENCY ACCEPTANCE DEMO")
    print(" Testing Rule: Two conflicting appointment requests must not both succeed")
    print("=" * 70)

    doctor = Doctor.objects.get(doctor_code="DOC-004")
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()
    if not slot:
        # Reset a slot if all booked
        slot = DoctorSlot.objects.filter(doctor=doctor).first()
        slot.is_available = True
        slot.save()
        Appointment.objects.filter(slot=slot).delete()

    patients = list(Patient.objects.all())

    # Obtain patient auth token
    client = APIClient()
    token_resp = client.post(
        "/api/v1/auth/token/",
        {"username": "patient.john", "password": "Patient@Password2026!"},
        format="json",
    )
    token = token_resp.data["access"]

    print(f"\n[TARGET DOCTOR] : {doctor.name} ({doctor.specialization})")
    print(f"[TARGET SLOT]   : {slot.start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"[DISPATCHING]   : 10 simultaneous threads competing for this exact slot...\n")

    num_threads = 10
    payload = {
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "patient_id": patients[0].id,
        "reason": "Concurrent race condition live drill",
    }

    def dispatch(idx):
        connection.close()
        t_client = APIClient()
        t_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        t_payload = payload.copy()
        t_payload["patient_id"] = patients[idx % len(patients)].id
        t_payload["notes"] = f"Thread-{idx}"

        resp = t_client.post("/api/v1/appointments/", t_payload, format="json")
        return idx, resp.status_code, resp.data

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(dispatch, i + 1) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda x: x[0])

    for thread_id, status_code, data in results:
        if status_code == 201:
            code = data.get("appointment_code", "")
            print(f" Thread {thread_id:02d} -> [HTTP {status_code} CREATED]  \u2714 BOOKED SUCCESS! (Code: {code})")
        elif status_code == 409:
            detail = data.get("detail", "Conflict")
            print(f" Thread {thread_id:02d} -> [HTTP {status_code} CONFLICT] \u2718 REJECTED: {detail}")
        else:
            print(f" Thread {thread_id:02d} -> [HTTP {status_code}] {data}")

    status_codes = [s for _, s, _ in results]
    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    print("\n" + "-" * 70)
    print(f" SUMMARY: Success (201): {success_count} | Conflicts (409): {conflict_count}")
    print("-" * 70)

    if success_count == 1 and conflict_count == num_threads - 1:
        print(" \u2705 VERIFICATION PASSED: Strict race-condition prevention guaranteed!")
        print("    Exactly ONE request succeeded. Double booking was strictly prevented.")
    else:
        print(" \u274c VERIFICATION FAILED!")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_concurrency_demonstration()
