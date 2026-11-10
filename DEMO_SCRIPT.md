# 3–5 Minute Video Demonstration Recording Script
**Hospital Management Platform | DevOps & Cloud Engineering**

Use this script as a guide to record your 3–5 minute video walkthrough (using Loom, OBS, or Zoom screen share).

---

## Video Outline & Time Allocation (Total: ~4 minutes)

| Segment | Duration | Focus Area | What to Show on Screen |
| :--- | :--- | :--- | :--- |
| **1. Introduction & Overview** | ~30 sec | Candidate intro & project scope | VS Code / GitHub Repository overview |
| **2. CI/CD Pipeline & Code Quality** | ~45 sec | GitHub Actions workflow & testing | GitHub Actions tab or local test suite run |
| **3. Container Deployment & Health** | ~60 sec | Docker Compose, TLS & Observability | Terminal running `docker compose ps` & curl |
| **4. Concurrency Acceptance Test** | ~60 sec | Core domain rule (no double booking) | Terminal running `python scripts/run_concurrency_demo.py` |
| **5. Failure Injection & Disaster Recovery** | ~45 sec | Chaos recovery & readiness probes | Terminal running `python scripts/test_failure_recovery.py` |

---

## Minute-by-Minute Script & Talking Points

### Minute 0:00 – 0:30: Introduction & Overview
* **Action**: Show your IDE (VS Code) with the project structure and `README.md`.
* **Talking Points**:
  > *"Hello, my name is [Your Name], and this is my individual project assessment submission for the DevOps & Cloud Engineering role: the Cloud Deployment and CI/CD Hospital Management Platform.*  
  > *My objective was to build a reproducibly buildable, observable, and recoverable service implementing a Doctor Appointment API using synthetic patient data.*  
  > *The platform is built using Python, Django REST Framework, and PostgreSQL 16, reverse-proxied with Nginx for TLS 1.3 encryption, and packaged in a multi-stage Dockerfile running as an unprivileged non-root user."*

---

### Minute 0:30 – 1:15: CI/CD Pipeline & Automated Testing
* **Action**: Switch to your terminal or GitHub Actions tab. Run the pytest test suite:
  ```bash
  python -m pytest -v
  ```
* **Talking Points**:
  > *"Here you can see our automated test suite running with pytest. It executes 17 comprehensive unit, integration, authentication, and concurrency tests in under 30 seconds.*  
  > *In our GitHub Actions workflow, every pull request triggers four automated stages: first, static linting and formatting with Flake8 and Black; second, security static analysis with Bandit; third, test execution with coverage; and fourth, a multi-stage Docker build scanned for container vulnerabilities using Trivy."*

---

### Minute 1:15 – 2:15: Container Deployment, HTTPS & Observability
* **Action**: Show the running containers and query the health endpoints:
  ```bash
  # Check running containers
  docker compose ps

  # Test HTTPS readiness probe through reverse proxy
  curl -k https://localhost/health/readiness/

  # Show Prometheus metrics
  curl -k https://localhost/metrics/
  ```
* **Talking Points**:
  > *"Our service is orchestrated using Docker Compose across two isolated networks: an external proxy network, and an isolated internal database network where PostgreSQL has no public host ports exposed.*  
  > *Nginx terminates SSL/TLS on port 443 with security headers and redirects all port 80 traffic to HTTPS.*  
  > *Our health check probes provide deep observability: `/health/liveness/` verifies the application process, and `/health/readiness/` validates the downstream database connection latency.*  
  > *We also achieve the rubric's stretch goal by exposing full Prometheus metrics on `/metrics/`."*

---

### Minute 2:15 – 3:15: The Concurrency Acceptance Demonstration
* **Action**: Run the live concurrency demonstration script:
  ```bash
  python scripts/run_concurrency_demo.py
  ```
* **Talking Points**:
  > *"Now let's demonstrate the core acceptance rule: two conflicting appointment requests must not both succeed.*  
  > *I am executing our standalone concurrency demonstration script, which dispatches 10 simultaneous threads competing to book the exact same doctor and time slot.*  
  > *As you can see on the screen: Thread 1 acquired the atomic row-level lock using Django's `select_for_update` and succeeded with HTTP 201 Created.*  
  > *All other 9 concurrent threads were rejected with HTTP 409 Conflict. The database contains exactly one confirmed appointment, strictly preventing double bookings under high load."*

---

### Minute 3:15 – 4:00: Failure Detection & Disaster Recovery
* **Action**: Run the failure recovery drill script:
  ```bash
  python scripts/test_failure_recovery.py
  ```
* **Talking Points**:
  > *"Finally, we demonstrate failure detection and recovery.*  
  > *The script first confirms the baseline health status is HTTP 200 OK.*  
  > *Next, it simulates a critical database dependency outage. Notice how the readiness probe immediately catches the disconnection and returns HTTP 503 Service Unavailable with structured error diagnosis.*  
  > *When the database is restored, the probe automatically detects the recovery and returns to HTTP 200 OK without manual intervention.*  
  > *In addition, our automated backup script computes SHA256 checksums and prunes archives according to our retention policy, ensuring deterministic disaster recovery.*  
  > *Thank you for reviewing my submission."*

---

## Tips for Recording
1. **Speak clearly and at a steady pace**: 3–5 minutes is plenty of time when following this structure.
2. **Increase terminal font size**: Ensure reviewers can easily read the terminal outputs and HTTP status codes (`200`, `201`, `409`, `503`).
3. **Verify video permissions**: If uploading to YouTube, set to **Unlisted** (not Private). If using Loom or Google Drive, ensure **Anyone with the link can view**.

