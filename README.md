# Cloud Deployment & CI/CD – Hospital Management Platform
**DevOps & Cloud Engineering | Production-Grade Appointment Scheduling Service**

[![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](#cicd-pipeline--automation)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Framework-Django%204.2%20LTS%20%2F%20DRF-green.svg)](https://www.djangoproject.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%2016-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Container-Multi--Stage%20Non--Root-orange.svg)](https://www.docker.com/)
[![Security](https://img.shields.io/badge/Security-Trivy%20%7C%20Bandit%20%7C%20TLS%201.3-red.svg)](#security-least-privilege--compliance)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

---

## 1. Executive Summary & Domain Scope

This repository provides a reproducible, containerized, observable, and recoverable **Doctor Appointment Scheduling API** engineered according to production DevOps and cloud delivery standards. 

In strict compliance with the project assessment brief:
* **Allocated Service**: Doctor appointment scheduling API with synthetic patient data only (no real personal health information).
* **Deterministic Concurrency Guarantee**: Prevents two confirmed appointments for the same doctor and time slot, even under simultaneous high-concurrency race conditions.
* **Production Operations**: Multi-stage Docker containerization running under an unprivileged user, automated reverse proxy with TLS 1.3 HTTPS termination, automated health/readiness checks, structured JSON telemetry with request correlation IDs, Prometheus metrics, and automated disaster backup/recovery procedures.

---

## 2. Architecture & Networking Overview

The deployment follows a three-tier production architecture with network isolation:

```
[ Public HTTPS Traffic: Port 443 / HTTP: Port 80 ]
                       │
                       ▼
         ┌───────────────────────────┐
         │       Nginx Proxy         │  • TLS 1.2 / 1.3 Termination (HTTPS)
         │    (Reverse Proxy)        │  • Port 80 -> 443 Strict Redirect
         └─────────────┬─────────────┘  • IP Rate Limiting (20 req/s, burst 40)
                       │ (proxy-net)    • Security Headers (HSTS, CSP, X-Frame)
                       ▼
         ┌───────────────────────────┐
         │     Django REST API       │  • Gunicorn / Python 3.10 Runtime
         │  (Non-Root UID 10001)     │  • JWT Bearer Authentication & RBAC
         └─────────────┬─────────────┘  • Concurrency Row-Level Locks
                       │ (internal-net) • Structured JSON Logging + Metrics
                       ▼
         ┌───────────────────────────┐
         │    PostgreSQL 16 DB       │  • Isolated Internal Network (No Public Ports)
         │   (Persistent Storage)    │  • ACID Transactions & Row-Level Locking
         └───────────────────────────┘  • Automated Point-in-Time Backups
```

### Port Mappings & Network Segmentation
| Service | Container Name | Internal Port | External Port | Network Access | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Reverse Proxy** | `hospital-reverse-proxy` | 80, 443 | **80, 443** | Public Host | TLS termination, HTTPS redirect, rate limiting |
| **API Backend** | `hospital-api` | 8000 | *None* | `proxy-net`, `internal-net` | Doctor appointment service (Gunicorn) |
| **Database** | `hospital-db` | 5432 | *None* | `internal-net` (Isolated) | Persistent PostgreSQL storage (`postgres_data`) |

---

## 3. Technology Stack & Key Decisions

* **Language & Framework**: Python 3.10+, Django 4.2 LTS, Django REST Framework (DRF), SimpleJWT.
* **Database**: PostgreSQL 16 Alpine (with SQLite compatibility for zero-dependency local test execution).
* **Reverse Proxy**: Nginx 1.25 Alpine with custom self-signed/CA TLS certificates.
* **Containerization**: Multi-stage Dockerfile (`builder` $\rightarrow$ minimal `runner`) running as unprivileged user `appuser` (UID 10001).
* **Orchestration**: Docker Compose with health checks, restart policies, and resource constraints.
* **Observability**: Structured JSON logging (`X-Correlation-ID` header propagation) and Prometheus metrics `/metrics/`.
* **CI/CD**: GitHub Actions (Linting, Formatting, Static Security Analysis, Pytest with Concurrency validation, Docker Build & Trivy Scan).

---

## 4. Quick Start: Build, Run & Deploy

### Prerequisites
* Docker Engine 24+ & Docker Compose v2+
* *(Optional for local native execution)*: Python 3.10+, Git.

### Option A: Standard Production Run via Docker Compose (Recommended)
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/Hospital-Management-Platform.git
   cd Hospital-Management-Platform
   ```

2. **Generate TLS Certificates & Environment File**:
   ```bash
   # Windows PowerShell
   .\scripts\generate_certs.ps1
   Copy-Item .env.example .env

   # Linux / macOS Bash
   bash scripts/generate_certs.sh
   cp .env.example .env
   ```

3. **Build & Start Services**:
   ```bash
   docker compose up -d --build
   ```

4. **Verify Health & Logs**:
   ```bash
   # Check service readiness
   curl -k https://localhost/health/readiness/

   # Inspect real-time structured logs
   docker compose logs -f web
   ```

5. **Access Application**:
   * **HTTPS API Endpoint**: `https://localhost/api/v1/`
   * **Health Liveness Probe**: `https://localhost/health/liveness/`
   * **Health Readiness Probe**: `https://localhost/health/readiness/`
   * **Prometheus Metrics**: `https://localhost/metrics/`
   * **Django Admin**: `https://localhost/admin/`

---

### Option B: Local Native Developer Run (Without Docker)
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations and seed synthetic doctors, slots, and patients
python manage.py migrate
python manage.py seed_data

# 3. Start local development server
python manage.py runserver 0.0.0.0:8000
```

---

## 5. Environment Variables Reference (`.env.example`)

| Variable | Description | Default / Example Value |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Target environment tag | `production` / `development` |
| `DEBUG` | Django debug toggle (**Must be False in production**) | `False` |
| `JWT_SECRET_KEY` | Cryptographic key for signing JWT tokens | *Random 32+ character hex string* |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration lifetime | `60` |
| `DATABASE_URL` | PostgreSQL connection URI | `postgresql://app_user:app_secure_password@db:5432/hospital_db` |
| `POSTGRES_USER` | Database username | `app_user` |
| `POSTGRES_PASSWORD` | Database password | `app_secure_password_replace_me` |
| `POSTGRES_DB` | Database name | `hospital_db` |
| `ALLOWED_ORIGINS` | CORS permitted origins | `https://localhost,http://localhost` |

---

## 6. API Reference & Authentication

All patient and administrative endpoints are protected with standard RFC 7519 JWT Bearer tokens. Pass the token via HTTP header:
`Authorization: Bearer <access_token>`

### Seeded Role-Based Credentials
| Role | Username | Password | Email | Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@Password2026!` | `admin@hospital.example.com` | Full administrative access & audit log inspection |
| **Doctor** | `dr.smith` | `Doctor@Password2026!` | `alice.smith@hospital.example.com` | View doctor appointments & slots |
| **Patient** | `patient.john` | `Patient@Password2026!` | `john.doe.synthetic@hospital.example.com` | Book, reschedule, and cancel personal appointments |

### Primary Endpoints
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health/liveness/` | None | Process liveness probe |
| `GET` | `/health/readiness/` | None | Database connectivity & dependency check (200 / 503) |
| `GET` | `/metrics/` | None | Prometheus telemetry exposition |
| `POST` | `/api/v1/auth/token/` | None | Authenticate credentials & retrieve JWT token pair |
| `GET` | `/api/v1/doctors/` | Bearer | List active physicians and clinical specialties |
| `GET` | `/api/v1/doctors/{id}/slots/` | Bearer | List consultation time slots for a doctor |
| `GET` | `/api/v1/patients/` | Bearer | List synthetic patients (test references) |
| `POST` | `/api/v1/appointments/` | Bearer | Book a consultation slot (**Concurrency protected**) |
| `GET` | `/api/v1/appointments/` | Bearer | List appointments (Filtered by role / ownership) |
| `GET` | `/api/v1/appointments/{id}/` | Bearer | Get appointment details |
| `PUT` | `/api/v1/appointments/{id}/reschedule/` | Bearer | Reschedule to a new slot (Atomic slot swap) |
| `DELETE` | `/api/v1/appointments/{id}/cancel/` | Bearer | Cancel appointment and restore slot availability |
| `GET` | `/api/v1/audit-logs/` | Bearer (Admin) | Inspect immutable security and clinical audit logs |

---

## 7. Concurrency Safety & Race Condition Prevention

### The Problem
In medical appointment systems, simultaneous requests from multiple patients attempting to claim the same doctor's slot can result in double bookings if handled naively.

### The Solution: Multi-Layered Atomic Isolation
1. **Row-Level Write Locking (`select_for_update`)**:
   Inside an atomic database transaction (`transaction.atomic()`), the application locks the exact `DoctorSlot` row:
   ```python
   with transaction.atomic():
       slot = DoctorSlot.objects.select_for_update().filter(
           id=slot_id, doctor=doctor, is_available=True
       ).first()
       if not slot:
           raise ConflictError("Slot is already booked or unavailable.")
       slot.is_available = False
       slot.save(update_fields=['is_available'])
       Appointment.objects.create(...)
   ```
2. **Database Unique Constraints**:
   A composite constraint on `(doctor, start_time)` prevents duplicate active slots at the persistence layer.
3. **HTTP 409 Conflict Contract**:
   When competing threads hit the lock simultaneously, the first thread claims the slot (201 Created), while all subsequent threads encounter `is_available=False` and are rejected with **HTTP 409 Conflict**.

---

## 8. Automated Testing & Verification

Run the comprehensive test suite (17 automated unit, integration, and concurrency tests):

```bash
# Run pytest with code coverage
python -m pytest -v --cov=appointments --cov=core

# Run the live 10-thread Concurrency Demonstration
python scripts/run_concurrency_demo.py

# Run the Failure & Recovery Drill
python scripts/test_failure_recovery.py
```

---

## 9. Backup, Restore & Rollback Procedures

### Automated Database Backup
Takes a compressed snapshot of PostgreSQL (or SQLite), computes a SHA256 checksum for tamper verification, and enforces retention policy:
```bash
# PowerShell
.\scripts\backup.ps1

# Linux / Bash
bash scripts/backup.sh
```

### Database Restore & Disaster Recovery
Verifies the SHA256 checksum before restoration, restores data, and performs a live readiness probe:
```bash
# PowerShell (restores latest backup)
.\scripts\restore.ps1

# Linux / Bash
bash scripts/restore.sh backups/backup_pg_20261111_000000.sql.gz
```

### Container Rollback Procedure
Reverts the web service to a designated stable image tag or previous commit and verifies health probes:
```bash
# PowerShell
.\scripts\rollback.ps1 -TargetTag "v1.0.0"

# Linux / Bash
bash scripts/rollback.sh "v1.0.0"
```

For detailed incident response playbooks and operational procedures, refer to [**`RUNBOOK.md`**](file:///c:/Users/Asus/Desktop/Hospital-Management-Platform/RUNBOOK.md).

---

## 10. Submission Package Checklist

* [x] **Service Source**: Clean Django REST Framework implementation in `appointments/` and `core/`.
* [x] **Containerization**: Hardened multi-stage non-root `Dockerfile` & `docker-compose.yml`.
* [x] **CI/CD Pipeline**: GitHub Actions workflow (`.github/workflows/ci.yml`) covering linting, security scanning (`bandit`, `trivy`), tests, and build.
* [x] **Reverse Proxy & HTTPS**: Nginx reverse proxy with TLS 1.3 configuration in `nginx/nginx.conf`.
* [x] **Concurrency Acceptance**: Automated test (`tests/test_concurrency.py`) and demo script (`scripts/run_concurrency_demo.py`).
* [x] **Disaster Recovery**: Backup, restore, and rollback scripts with automated verification test (`tests/test_backup_restore.py`).
* [x] **Documentation & Runbook**: [ARCHITECTURE.md](file:///c:/Users/Asus/Desktop/Hospital-Management-Platform/ARCHITECTURE.md), [RUNBOOK.md](file:///c:/Users/Asus/Desktop/Hospital-Management-Platform/RUNBOOK.md), [EVIDENCE.md](file:///c:/Users/Asus/Desktop/Hospital-Management-Platform/EVIDENCE.md), [SUBMISSION.md](file:///c:/Users/Asus/Desktop/Hospital-Management-Platform/SUBMISSION.md), and [DEMO_SCRIPT.md](file:///c:/Users/Asus/Desktop/Hospital-Management-Platform/DEMO_SCRIPT.md).
