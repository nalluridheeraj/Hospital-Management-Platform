"""Automated Database Restore and Disaster Recovery Utility for Hospital Management Platform (Django).
Verifies SHA256 integrity checksum, restores tables, and validates database health.
"""

import os
import sys
import gzip
import shutil
import hashlib
import sqlite3
import subprocess
import time
from datetime import datetime

# Setup Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.conf import settings
from django.db import connection


def compute_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksum(backup_file: str) -> bool:
    checksum_file = backup_file + ".sha256"
    if not os.path.exists(checksum_file):
        print(f"[WARNING] Checksum file not found: {checksum_file}. Skipping checksum validation.")
        return True

    with open(checksum_file, "r") as f:
        expected = f.read().split()[0].strip()

    actual = compute_sha256(backup_file)
    if expected.lower() != actual.lower():
        print(f"[ERROR] Checksum MISMATCH! Expected: {expected}, Actual: {actual}")
        return False

    print(f"[VERIFIED] SHA256 Checksum verified: {actual}")
    return True


def restore_database(backup_file: str) -> bool:
    if not os.path.exists(backup_file):
        print(f"[ERROR] Backup file does not exist: {backup_file}")
        return False

    print(f"[{datetime.utcnow().isoformat()}] Starting database restore from {backup_file}...")

    # Step 1: Checksum Verification
    if not verify_checksum(backup_file):
        print("[ABORT] Database restore aborted due to integrity checksum mismatch!")
        return False

    db_config = settings.DATABASES["default"]
    engine = db_config["ENGINE"]

    if "sqlite3" in engine:
        db_file = str(db_config["NAME"])

        if os.path.exists(db_file):
            connection.close()
            time.sleep(0.3)
            with gzip.open(backup_file, "rb") as src, open(db_file, "wb") as dst:
                shutil.copyfileobj(src, dst)
        else:
            # In-memory database restore via native SQLite backup
            temp_restore = backup_file + ".tmp.db"
            with gzip.open(backup_file, "rb") as src, open(temp_restore, "wb") as dst:
                shutil.copyfileobj(src, dst)

            restore_conn = sqlite3.connect(temp_restore)
            connection.ensure_connection()
            restore_conn.backup(connection.connection)
            restore_conn.close()

            if os.path.exists(temp_restore):
                os.remove(temp_restore)

        print("[SUCCESS] SQLite database successfully restored!")

    else:
        # PostgreSQL Restore
        db_user = db_config.get("USER") or "app_user"
        db_pass = db_config.get("PASSWORD") or ""
        db_host = db_config.get("HOST") or "localhost"
        db_port = str(db_config.get("PORT") or 5432)
        db_name = db_config.get("NAME") or "hospital_db"

        env = os.environ.copy()
        if db_pass:
            env["PGPASSWORD"] = db_pass

        with gzip.open(backup_file, "rb") as f_in:
            sql_data = f_in.read()

        try:
            cmd = ["psql", "-h", db_host, "-p", db_port, "-U", db_user, "-d", db_name]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            stdout, stderr = p.communicate(input=sql_data)
            if p.returncode != 0:
                print(f"[ERROR] psql failed: {stderr.decode('utf-8')}")
                return False
        except FileNotFoundError:
            print("Local psql not found. Executing restore via Docker container 'hospital-db'...")
            docker_cmd = ["docker", "exec", "-i", "hospital-db", "psql", "-U", db_user, "-d", db_name]
            p_docker = subprocess.Popen(docker_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p_docker.communicate(input=sql_data)
            if p_docker.returncode != 0:
                print(f"[ERROR] Docker psql failed: {stderr.decode('utf-8')}")
                return False

    # Step 2: Post-Restore Verification
    try:
        connection.connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("[SUCCESS] Database restore complete and connection verified healthy!")
        return True
    except Exception as e:
        print(f"[ERROR] Database restore finished but health verification failed: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            print("No backups directory found.")
            sys.exit(1)
        backups = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".gz")],
            key=os.path.getctime,
        )
        if not backups:
            print("No backup files found in backups/")
            sys.exit(1)
        target = backups[-1]
        print(f"No file specified. Using latest backup: {target}")
    else:
        target = sys.argv[1]

    ok = restore_database(target)
    sys.exit(0 if ok else 1)
