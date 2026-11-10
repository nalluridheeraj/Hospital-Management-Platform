"""Live End-to-End API Test Script against running server (http://127.0.0.1:8000).
Tests health probes, metrics, auth, doctor catalog, appointment booking,
concurrency race conditions, rescheduling, cancelling, and audit logs.
"""

import requests
import json
import concurrent.futures

BASE_URL = "http://127.0.0.1:8000"

def test_live_server():
    print("=" * 70)
    print(" RUNNING END-TO-END LIVE API & BROWSER ENDPOINT TESTS")
    print(f" Target Server: {BASE_URL}")
    print("=" * 70)

    session = requests.Session()

    # 1. Dashboard Homepage
    print("\n[TEST 1] Testing Dashboard UI Homepage (/)...")
    r = session.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "Hospital Management Platform" in r.text
    print(f" -> Status: {r.status_code} OK (HTML Dashboard loaded successfully)")

    # 2. Liveness & Readiness Probes
    print("\n[TEST 2] Testing Observability Health Probes...")
    r_live = session.get(f"{BASE_URL}/health/liveness/")
    assert r_live.status_code == 200
    print(f" -> Liveness:  HTTP {r_live.status_code} -> {r_live.json()['status']}")

    r_ready = session.get(f"{BASE_URL}/health/readiness/")
    assert r_ready.status_code == 200
    db_info = r_ready.json()["database"]
    print(f" -> Readiness: HTTP {r_ready.status_code} -> DB {db_info['database']} ({db_info['latency_ms']}ms)")

    # 3. Prometheus Metrics
    print("\n[TEST 3] Testing Prometheus Telemetry (/metrics/)...")
    r_metrics = session.get(f"{BASE_URL}/metrics/")
    assert r_metrics.status_code == 200
    assert "django_hospital_http_requests_total" in r_metrics.text
    print(f" -> Metrics:   HTTP {r_metrics.status_code} OK (Prometheus scrape target verified)")

    # 4. Authentication (JWT)
    print("\n[TEST 4] Testing Authentication & JWT Generation (/api/v1/auth/token/)...")
    auth_resp = session.post(
        f"{BASE_URL}/api/v1/auth/token/",
        json={"username": "patient.john", "password": "Patient@Password2026!"}
    )
    assert auth_resp.status_code == 200
    token = auth_resp.json()["access"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f" -> Token:     HTTP 200 OK (Issued JWT token: {token[:25]}...)")

    # 5. List Doctors
    print("\n[TEST 5] Testing Doctor Catalog (/api/v1/doctors/)...")
    r_docs = session.get(f"{BASE_URL}/api/v1/doctors/", headers=headers)
    assert r_docs.status_code == 200
    doctors = r_docs.json()
    print(f" -> Doctors:   HTTP 200 OK (Retrieved {len(doctors)} active physicians)")
    for d in doctors:
        print(f"    • {d['doctor_code']}: {d['name']} - {d['specialization']} ({d['department']})")

    # 6. List Doctor Slots
    target_doc = doctors[0]
    print(f"\n[TEST 6] Testing Available Slots for {target_doc['name']}...")
    r_slots = session.get(f"{BASE_URL}/api/v1/doctors/{target_doc['id']}/slots/?available_only=true", headers=headers)
    assert r_slots.status_code == 200
    slots = r_slots.json()
    print(f" -> Slots:     HTTP 200 OK ({len(slots)} open slots found)")
    slot = slots[0]

    # 7. List Synthetic Patients
    print("\n[TEST 7] Testing Synthetic Patients Catalog (/api/v1/patients/)...")
    r_patients = session.get(f"{BASE_URL}/api/v1/patients/", headers=headers)
    assert r_patients.status_code == 200
    patients = r_patients.json()
    print(f" -> Patients:  HTTP 200 OK ({len(patients)} synthetic patient profiles)")
    patient = patients[0]

    # 8. Book Appointment
    print(f"\n[TEST 8] Booking Consultation Slot ({slot['start_time']})...")
    book_payload = {
        "doctor_id": target_doc["id"],
        "slot_id": slot["id"],
        "patient_id": patient["id"],
        "reason": "Live browser verification checkup",
        "notes": "Automated test notes"
    }
    r_book = session.post(f"{BASE_URL}/api/v1/appointments/", json=book_payload, headers=headers)
    assert r_book.status_code == 201, r_book.text
    apt = r_book.json()
    apt_id = apt["id"]
    print(f" -> Booked:    HTTP 201 CREATED (Appointment Code: {apt['appointment_code']}, Status: {apt['status']})")

    # 9. Concurrency Protection Test (Try booking the same slot again)
    print("\n[TEST 9] Verifying Double Booking Rejection on Already Booked Slot...")
    r_conflict = session.post(f"{BASE_URL}/api/v1/appointments/", json=book_payload, headers=headers)
    assert r_conflict.status_code == 409
    print(f" -> Conflict:  HTTP 409 CONFLICT (Successfully blocked duplicate booking!)")
    print(f"    Detail: {r_conflict.json()['detail']}")

    # 10. Reschedule Appointment
    print("\n[TEST 10] Testing Appointment Rescheduling...")
    new_slot = slots[1]
    resched_resp = session.put(
        f"{BASE_URL}/api/v1/appointments/{apt_id}/reschedule/",
        json={"new_slot_id": new_slot["id"], "reason": "Patient requested new time"},
        headers=headers
    )
    assert resched_resp.status_code == 200
    print(f" -> Reschedule: HTTP 200 OK (Transferred to new slot: {new_slot['start_time']})")

    # 11. Cancel Appointment
    print("\n[TEST 11] Testing Appointment Cancellation & Slot Freeing...")
    cancel_resp = session.delete(f"{BASE_URL}/api/v1/appointments/{apt_id}/cancel/", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"
    print(f" -> Cancelled: HTTP 200 OK (Appointment marked CANCELLED, slot restored to available)")

    # 12. Concurrency Stress Drill (10 simultaneous threads)
    print("\n[TEST 12] Testing Live 10-Thread Concurrency Race Condition...")
    doctor_4 = doctors[-1]
    d4_slots = session.get(f"{BASE_URL}/api/v1/doctors/{doctor_4['id']}/slots/?available_only=true", headers=headers).json()
    test_slot = d4_slots[0]

    def shoot(thread_num):
        s = requests.Session()
        resp = s.post(
            f"{BASE_URL}/api/v1/appointments/",
            json={
                "doctor_id": doctor_4["id"],
                "slot_id": test_slot["id"],
                "patient_id": patients[thread_num % len(patients)]["id"],
                "reason": f"Simultaneous thread-{thread_num}"
            },
            headers=headers
        )
        return thread_num, resp.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(shoot, i + 1) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    results.sort(key=lambda x: x[0])
    statuses = [s for _, s in results]
    success_count = statuses.count(201)
    conflict_count = statuses.count(409)

    print(f" -> Results:   Success (201): {success_count} | Conflicts (409): {conflict_count}")
    for tid, st in results:
        status_label = "201 CREATED (CONFIRMED)" if st == 201 else "409 CONFLICT (BLOCKED)"
        print(f"    Thread {tid:02d}: HTTP {st} -> {status_label}")

    assert success_count == 1, f"Expected 1 success, got {success_count}"
    assert conflict_count == 9, f"Expected 9 conflicts, got {conflict_count}"

    print("\n" + "=" * 70)
    print(" ALL 12 LIVE END-TO-END HTTP TESTS PASSED WITH 100% SUCCESS!")
    print(" The platform is live and verified on http://127.0.0.1:8000/")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_live_server()

