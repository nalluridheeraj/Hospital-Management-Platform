# Technical Walkthrough & Live Debugging Playbook
**Cloud Deployment & CI/CD – Hospital Management Platform**  
**Preparation Guide for the 15-Minute Walkthrough & 10-Minute Live Debugging Task**

---

## 1. Overview of the Assessment Interview

The evaluation brief specifies:
> *"Shortlisted candidates will attend a 15-minute technical walkthrough and a 10-minute live change/debugging task. You must explain your own architecture and modify your own work."*
> *"Your submission is evaluated on evidence of engineering ability, problem-solving, correctness and ownership."*

This guide ensures you can confidently explain every architectural decision, demonstrate your mastery of the codebase, and effortlessly complete live code modifications under examination.

---

## 2. Structure of the 15-Minute Technical Walkthrough

| Time | Topic | What to Say & Show |
| :--- | :--- | :--- |
| **0:00–3:00** | **Architecture & Stack** | Explain the 3-tier isolated architecture: Nginx (TLS 1.3 reverse proxy) $\rightarrow$ Django REST API (Gunicorn, non-root `appuser`) $\rightarrow$ PostgreSQL 16 (isolated internal network). |
| **3:00–7:00** | **Concurrency & Race Conditions** | Open `appointments/views.py`. Walk through `create()` and explain why `select_for_update()` inside `transaction.atomic()` strictly prevents double bookings. Show `scripts/run_concurrency_demo.py`. |
| **7:00–10:00** | **Containerization & CI/CD** | Walk through the multi-stage `Dockerfile` (builder $\rightarrow$ runner, UID 10001) and `.github/workflows/ci.yml` (Flake8, Black, Bandit, Pytest, Trivy scan). |
| **10:00–13:00** | **Observability & Disaster Recovery** | Show `/health/readiness/` (DB connectivity check) and structured JSON logging with `X-Correlation-ID`. Explain the backup/restore SHA256 integrity verification. |
| **13:00–15:00** | **Reviewer Q&A** | Answer technical questions with clarity and precision. |

---

## 3. High-Probability Reviewer Questions & Model Answers

### Q1: *"Why did you use `select_for_update()` instead of a simple `if slot.is_available:` check in Python?"*
> **Model Answer**:  
> *"If we only check `if slot.is_available` in Python, we introduce a **Time-Of-Check to Time-Of-Use (TOCTOU) race condition**. If two requests arrive simultaneously, both threads could execute the `SELECT` query before either has saved the update. Both would see `is_available=True` and both would proceed to confirm the booking, resulting in a critical double booking.  
> By using Django's `select_for_update()` inside `transaction.atomic()`, the database acquires an exclusive row-level write lock (`SELECT ... FOR UPDATE` in PostgreSQL). The second transaction is forced to wait until the first commits, at which point it encounters `is_available=False` and is rejected with an HTTP 409 Conflict."*

### Q2: *"Why run the Docker container as an unprivileged user (`appuser`, UID 10001)?"*
> **Model Answer**:  
> *"In accordance with the **Principle of Least Privilege**, processes inside a container should never run as root unless strictly required. If an application vulnerability (such as remote code execution) were exploited, running as root would grant the attacker root capabilities inside the container, increasing the risk of a container breakout to the host kernel. Creating `appuser` with UID 10001 ensures the process has only the minimal filesystem access required to run."*

### Q3: *"Explain your network isolation strategy in Docker Compose."*
> **Model Answer**:  
> *"We use two separate Docker bridge networks:  
> 1. `proxy-net`: Connects Nginx to the Django API service. Only Nginx binds external host ports (80 and 443).  
> 2. `internal-net`: Connects the Django API to PostgreSQL. It is marked `internal: true`.  
> Crucially, PostgreSQL's port `5432` is not bound to the host network at all. The database cannot be reached from the public internet or host interfaces, protecting it from brute-force attacks and port scanning."*

### Q4: *"What is the difference between your `/health/liveness/` and `/health/readiness/` probes?"*
> **Model Answer**:  
> *"The **Liveness probe** (`/health/liveness/`) checks whether the web server process itself is running and responding to HTTP requests. If this fails, the container orchestrator should restart the container.  
> The **Readiness probe** (`/health/readiness/`) validates whether downstream dependencies—specifically the PostgreSQL database—are responsive by executing `SELECT 1`. If the database is disconnected, readiness returns HTTP 503, signaling that traffic should not be routed to this instance while keeping the container alive for automatic recovery."*

### Q5: *"How do you guarantee backup integrity and prevent silent data corruption?"*
> **Model Answer**:  
> *"Our backup script (`scripts/backup.py`) computes a cryptographic **SHA256 checksum** immediately after taking the compressed database dump and stores it in a companion `.sha256` manifest.  
> Before any restoration begins (`scripts/restore.py`), the script re-computes the checksum and verifies it against the manifest. If a single bit is corrupted or tampered with, the restore operation aborts immediately."*

---

## 4. The 10-Minute Live Change / Debugging Playbook

During the interview, the reviewer will give you a live change or debugging challenge. Below are the 5 most common requests with exact step-by-step solutions:

---

### Challenge 1: *"Add a cancellation reason field when cancelling an appointment"*

**File to Modify**: `appointments/views.py` (Line ~330)

**Step 1**: In `appointments/views.py`, locate the `cancel()` method inside `AppointmentViewSet`.  
**Step 2**: Update the method to accept `reason` from `request.data`:

```python
    @action(detail=True, methods=["delete", "post"], url_path="cancel")
    def cancel(self, request, pk=None):
        appointment = self.get_object()

        if appointment.status == Appointment.STATUS_CANCELLED:
            return Response(
                {"detail": "Appointment is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract cancellation reason from request body
        cancel_reason = request.data.get("reason", "Cancelled by user")

        with transaction.atomic():
            slot = appointment.slot
            slot.is_available = True
            slot.save(update_fields=["is_available"])

            appointment.status = Appointment.STATUS_CANCELLED
            appointment.notes = f"{appointment.notes or ''} [Cancelled: {cancel_reason}]"
            appointment.save(update_fields=["status", "notes"])

        log_audit_event(
            actor_id=request.user.username,
            actor_role="patient" if not request.user.is_staff else "admin",
            action="APPOINTMENT_CANCELLED",
            resource_type="appointment",
            resource_id=appointment.id,
            details=f"Appointment {appointment.appointment_code} cancelled. Reason: {cancel_reason}",
            status="SUCCESS",
        )

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_200_OK)
```

---

### Challenge 2: *"Change doctor consultation slot duration from 45 min to 30 min"*

**File to Modify**: `appointments/management/commands/seed_data.py` (Line ~95)

**Change**:
```python
# Change from timedelta(minutes=45) to timedelta(minutes=30)
end_dt = start_dt + timedelta(minutes=30)
```

**Apply in Terminal**:
```bash
python manage.py seed_data --force
```

---

### Challenge 3: *"Expose a new Prometheus metric tracking appointment cancellations"*

**File to Modify**: `appointments/views.py` (Line ~30)

**Step 1**: Check the existing Prometheus metric:
```python
APPOINTMENT_OPERATIONS = Counter(
    "django_hospital_appointment_operations_total",
    "Total appointment lifecycle operations",
    ["operation", "status"],
)
```

**Step 2**: Add a dedicated counter if requested:
```python
APPOINTMENT_CANCELLATIONS_TOTAL = Counter(
    "django_hospital_appointment_cancellations_total",
    "Total count of cancelled appointments",
)
```

**Step 3**: Inside the `cancel()` method, increment it:
```python
APPOINTMENT_CANCELLATIONS_TOTAL.inc()
```

---

### Challenge 4: *"Increase the Nginx rate limit from 20 req/s to 50 req/s"*

**File to Modify**: `nginx/nginx.conf` (Line ~32)

**Change**:
```nginx
# Change from rate=20r/s to rate=50r/s
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=50r/s;
```

**Apply without Downtime**:
```bash
docker compose exec proxy nginx -s reload
```

---

### Challenge 5: *"Simulate and diagnose a database outage live"*

**Step 1**: Run the automated drill:
```bash
python scripts/test_failure_recovery.py
```
**Step 2**: Explain what is happening on screen:
1. Baseline query returns `200 OK` (healthy).
2. The database connection is interrupted.
3. The readiness probe catches the error and returns `503 Service Unavailable` with `database: "disconnected"`.
4. When restored, the probe immediately transitions back to `200 OK`.
