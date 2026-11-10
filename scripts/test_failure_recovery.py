"""Failure Detection and Disaster Recovery Demonstration Script.
Tests:
1. Baseline health probe (HTTP 200)
2. Injected failure detection (HTTP 503)
3. Automated service recovery & health restoration (HTTP 200)
"""

import os
import sys
import time
import subprocess
import requests

HEALTH_URL = "http://localhost:8000/health/readiness/"
# Alternative for reverse proxy HTTPS:
HTTPS_HEALTH_URL = "https://localhost/health/readiness/"


def check_health(url):
    try:
        resp = requests.get(url, timeout=3, verify=False)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def run_failure_recovery_drill():
    print("=" * 70)
    print(" DISASTER RECOVERY DRILL: SERVICE BREAKAGE & DETECTION")
    print("=" * 70)

    # Step 1: Baseline Health Check
    print("\n[STEP 1/3] Checking Baseline Health Status...")
    status_code, data = check_health(HEALTH_URL)
    print(f" -> Probe URL: {HEALTH_URL}")
    print(f" -> Response Code: {status_code}")
    print(f" -> Payload: {data}")

    if status_code != 200:
        print("[NOTICE] Application not currently running on localhost:8000.")
        print("Starting simulated DB outage drill internally via Django database check...")
        _run_internal_failure_drill()
        return

    print(" \u2705 Baseline health verified: Service is READY and receiving traffic.")

    # Step 2: Inject Failure (Stop Database)
    print("\n[STEP 2/3] Simulating Critical Dependency Outage: Stopping 'hospital-db' container...")
    try:
        subprocess.run(["docker", "stop", "hospital-db"], check=True)
        print(" -> Container 'hospital-db' stopped.")
    except Exception as e:
        print(f" -> Could not stop container: {e}")

    time.sleep(2)

    print(" -> Probing readiness probe during outage...")
    status_code, data = check_health(HEALTH_URL)
    print(f" -> Response Code: {status_code}")
    print(f" -> Payload: {data}")

    if status_code == 503:
        print(" \u2705 FAILURE DETECTED: Readiness probe correctly caught database failure and returned HTTP 503!")
    else:
        print(f" -> Unexpected response: {status_code}")

    # Step 3: Service Recovery
    print("\n[STEP 3/3] Recovering Dependency: Restarting 'hospital-db' container...")
    try:
        subprocess.run(["docker", "start", "hospital-db"], check=True)
        print(" -> Container 'hospital-db' restarted.")
    except Exception as e:
        print(f" -> Could not restart container: {e}")

    print(" -> Polling readiness probe until service recovers...")
    for i in range(15):
        time.sleep(2)
        status_code, data = check_health(HEALTH_URL)
        if status_code == 200:
            print(f" -> Attempt {i+1}: HTTP 200 OK - Recovered!")
            print(f" -> Payload: {data}")
            print(" \u2705 RECOVERY VERIFIED: Service successfully recovered to READY state.")
            print("=" * 70 + "\n")
            return

    print(" \u274c Service failed to recover within timeout.")
    print("=" * 70 + "\n")


def _run_internal_failure_drill():
    # Setup Django
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django
    django.setup()
    from django.db import connection
    from rest_framework.test import APIClient

    client = APIClient()

    # 1. Healthy probe
    resp1 = client.get("/health/readiness/")
    print(f" -> Baseline Probe: HTTP {resp1.status_code}")
    print(f" -> Status: {resp1.data}")
    assert resp1.status_code == 200

    # 2. Simulate broken DB by closing connection and breaking host
    print("\n -> Breaking database connection...")
    old_engine = connection.settings_dict["NAME"]
    connection.settings_dict["NAME"] = "invalid_path_unreachable/corrupt.db"
    connection.close()

    resp2 = client.get("/health/readiness/")
    print(f" -> Outage Probe: HTTP {resp2.status_code} (Expected 503)")
    print(f" -> Status: {resp2.data}")
    assert resp2.status_code == 503
    print(" \u2705 FAILURE DETECTED: Service returned HTTP 503 with diagnostic error.")

    # 3. Recover
    print("\n -> Restoring database connection...")
    connection.settings_dict["NAME"] = old_engine
    connection.close()

    resp3 = client.get("/health/readiness/")
    print(f" -> Recovery Probe: HTTP {resp3.status_code} (Expected 200)")
    print(f" -> Status: {resp3.data}")
    assert resp3.status_code == 200
    print(" \u2705 RECOVERY VERIFIED: Service recovered to READY state!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_failure_recovery_drill()
