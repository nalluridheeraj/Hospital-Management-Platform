# Operations Runbook - Hospital Management Platform
**Standard Operating Procedures (SOP), Monitoring, Disaster Recovery & Incident Response**

---

## 1. Service Deployment & Operations

### Standard Cold Deployment
```bash
# 1. Ensure certificates and .env exist
python scripts/generate_certs.py nginx/certs
cp .env.example .env

# 2. Build and launch services detached
docker compose up -d --build

# 3. Verify container state
docker compose ps
```

### Graceful Restart
```bash
# Restart application layer without restarting database
docker compose restart web

# Restart reverse proxy
docker compose restart proxy

# Full restart
docker compose restart
```

### Zero-Downtime Rolling Update
```bash
# Pull or build latest version tag
docker compose build web

# Recreate web container seamlessly
docker compose up -d --no-deps --build web
```

---

## 2. Health Monitoring & Observability

### Endpoint Status Matrix
| Endpoint | Expected Status | Purpose | Action if Failing |
| :--- | :--- | :--- | :--- |
| `https://localhost/health/liveness/` | `HTTP 200 OK` | Process is running | Check container logs: `docker compose logs web` |
| `https://localhost/health/readiness/` | `HTTP 200 OK` | Downstream DB connectivity verified | Inspect DB container: `docker compose logs db` |
| `https://localhost/metrics/` | `HTTP 200 OK` | Prometheus scrape target | Verify Prometheus client configuration |

### Structured Log Inspection
The application emits structured single-line JSON logs containing request correlation IDs, latency in milliseconds, status codes, and client IPs:

```bash
# Stream real-time structured application logs
docker compose logs -f web

# Filter logs for errors only
docker compose logs web | grep '"level": "ERROR"'

# Track a specific user request using its Correlation ID
docker compose logs web | grep "correlation_id_here"

# Inspect Nginx reverse proxy access logs
docker compose logs -f proxy
```

---

## 3. Automated Backup Procedure

### Automated Execution
Backups are executed via Python, Bash, or PowerShell scripts, producing compressed gzip archives accompanied by SHA256 checksums:

```bash
# Windows PowerShell
.\scripts\backup.ps1

# Linux / Bash
bash scripts/backup.sh

# Python CLI Direct
python scripts/backup.py backups
```

### Verification Checklist
1. Confirm backup archive exists: `backups/backup_pg_<timestamp>.sql.gz` (or `backup_sqlite_...`).
2. Confirm SHA256 checksum exists: `backups/backup_pg_<timestamp>.sql.gz.sha256`.
3. Verify file integrity:
   ```bash
   sha256sum -c backups/backup_pg_<timestamp>.sql.gz.sha256
   ```
4. Verify retention policy has pruned archives older than the 10-backup threshold.

---

## 4. Disaster Recovery & Database Restoration

In the event of database corruption, data loss, or accidental deletion:

```bash
# Step 1: Identify latest verified backup file
ls -la backups/

# Step 2: Execute automated restore
# Windows PowerShell
.\scripts\restore.ps1 -BackupFile "backups\backup_pg_20261111_000000.sql.gz"

# Linux / Bash
bash scripts/restore.sh backups/backup_pg_20261111_000000.sql.gz

# Step 3: Verify system health post-restore
curl -k https://localhost/health/readiness/
```

The restore script automatically:
* Verifies the SHA256 checksum against the `.sha256` manifest.
* Aborts if tampering or bitrot is detected.
* Restores the schema and rows.
* Executes a live `SELECT 1` query to verify database health.

---

## 5. Emergency Rollback Procedure

If a new deployment exhibits regressions, performance degradation, or failures:

```bash
# Windows PowerShell
.\scripts\rollback.ps1 -TargetTag "v1.0.0"

# Linux / Bash
bash scripts/rollback.sh "v1.0.0"
```

### Rollback Workflow
1. The rollback script stops the failing `web` container.
2. Sets `IMAGE_TAG` to the designated stable target.
3. Relaunches the container (`docker compose up -d --no-deps web`).
4. Polls the `/health/readiness/` probe for up to 30 seconds.
5. If the probe confirms `HTTP 200 OK`, rollback succeeds; otherwise, recent container logs are displayed for escalation.

---

## 6. Incident Response Playbooks

### Playbook 1: Readiness Probe Returns HTTP 503 (Database Disconnected)
* **Symptom**: `/health/readiness/` returns `503 Service Unavailable`, `database: "disconnected"`.
* **Diagnosis**:
  ```bash
  # Check database container status
  docker compose ps db
  docker compose logs db --tail=50
  ```
* **Mitigation**:
  1. Restart database container: `docker compose restart db`.
  2. If data volume is corrupt, restore latest verified backup:
     `bash scripts/restore.sh`
  3. Confirm recovery: `curl -k https://localhost/health/readiness/`.

---

### Playbook 2: Spike in HTTP 409 Conflict Errors
* **Symptom**: Clients report `409 Conflict` on appointment booking.
* **Diagnosis**:
  1. This is the **intended behavior** when multiple patients simultaneously attempt to claim the exact same doctor and slot.
  2. Inspect audit logs:
     ```bash
     curl -k -H "Authorization: Bearer <admin_token>" https://localhost/api/v1/audit-logs/?action=APPOINTMENT_CONFLICT
     ```
* **Mitigation**:
  * Verify whether doctors have sufficient upcoming slots seeded.
  * If slots are exhausted, seed additional consultation windows:
    `python manage.py seed_data`

---

### Playbook 3: TLS / SSL Handshake Failures
* **Symptom**: Browser or client rejects HTTPS connection with certificate error.
* **Diagnosis**:
  ```bash
  openssl s_client -connect localhost:443 -servername localhost
  ```
* **Mitigation**:
  1. Regenerate local certificates:
     `python scripts/generate_certs.py nginx/certs`
  2. Reload Nginx configuration:
     `docker compose exec proxy nginx -s reload`
  3. Ensure clients trust the local development CA or use `--insecure` / `-k` for local drills.

---

### Playbook 4: Container Out-Of-Memory (OOM) or CrashLoop
* **Symptom**: `hospital-api` exits unexpectedly with code `137`.
* **Diagnosis**:
  ```bash
  docker inspect hospital-api --format='{{.State.OOMKilled}}'
  ```
* **Mitigation**:
  1. Increase memory limit in `docker-compose.yml` (`limits.memory: 1G`).
  2. Apply changes: `docker compose up -d web`.

