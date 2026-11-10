"""Automated Database Backup Utility for Hospital Management Platform (Django).
Supports PostgreSQL (production) and SQLite (testing/local).
Includes SHA256 checksum generation and retention pruning.
"""

import os
import sys
import gzip
import shutil
import hashlib
import sqlite3
import subprocess
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


def backup_database(output_dir: str = "backups", retention_count: int = 10) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db_config = settings.DATABASES["default"]
    engine = db_config["ENGINE"]

    print(f"[{datetime.utcnow().isoformat()}] Starting database backup ({engine})...")

    if "sqlite3" in engine:
        db_file = str(db_config["NAME"])
        backup_file = os.path.join(output_dir, f"backup_sqlite_{timestamp}.db.gz")
        temp_raw = os.path.join(output_dir, f"temp_raw_{timestamp}.db")

        if os.path.exists(db_file):
            with open(db_file, "rb") as src, gzip.open(backup_file, "wb") as dst:
                shutil.copyfileobj(src, dst)
        else:
            # In-memory SQLite database: use SQLite native backup API
            raw_conn = sqlite3.connect(temp_raw)
            connection.ensure_connection()
            connection.connection.backup(raw_conn)
            raw_conn.close()

            with open(temp_raw, "rb") as src, gzip.open(backup_file, "wb") as dst:
                shutil.copyfileobj(src, dst)

            if os.path.exists(temp_raw):
                os.remove(temp_raw)

    else:
        # PostgreSQL Backup
        db_user = db_config.get("USER") or "app_user"
        db_pass = db_config.get("PASSWORD") or ""
        db_host = db_config.get("HOST") or "localhost"
        db_port = str(db_config.get("PORT") or 5432)
        db_name = db_config.get("NAME") or "hospital_db"

        backup_file = os.path.join(output_dir, f"backup_pg_{timestamp}.sql.gz")
        env = os.environ.copy()
        if db_pass:
            env["PGPASSWORD"] = db_pass

        cmd = [
            "pg_dump",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "--no-owner",
            "--clean",
            "--if-exists",
        ]

        try:
            p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env)
            with gzip.open(backup_file, "wb") as f_out:
                shutil.copyfileobj(p1.stdout, f_out)
            p1.wait()
            if p1.returncode != 0:
                raise RuntimeError(f"pg_dump failed with exit code {p1.returncode}")
        except FileNotFoundError:
            print("Local pg_dump not found. Executing backup via Docker container 'hospital-db'...")
            docker_cmd = [
                "docker", "exec", "hospital-db",
                "pg_dump", "-U", db_user, "-d", db_name, "--clean", "--if-exists"
            ]
            p_docker = subprocess.Popen(docker_cmd, stdout=subprocess.PIPE)
            with gzip.open(backup_file, "wb") as f_out:
                shutil.copyfileobj(p_docker.stdout, f_out)
            p_docker.wait()
            if p_docker.returncode != 0:
                raise RuntimeError(f"Docker pg_dump failed with exit code {p_docker.returncode}")

    # Compute SHA256 checksum
    checksum = compute_sha256(backup_file)
    checksum_file = backup_file + ".sha256"
    with open(checksum_file, "w") as f:
        f.write(f"{checksum}  {os.path.basename(backup_file)}\n")

    size_bytes = os.path.getsize(backup_file)
    print(f"[SUCCESS] Backup created: {backup_file} ({size_bytes} bytes)")
    print(f"[SUCCESS] SHA256 Checksum: {checksum}")

    # Retention Policy Pruning
    all_backups = sorted(
        [
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.endswith(".gz") and (f.startswith("backup_pg_") or f.startswith("backup_sqlite_"))
        ],
        key=os.path.getctime,
    )

    if len(all_backups) > retention_count:
        to_prune = all_backups[:-retention_count]
        for old_file in to_prune:
            try:
                os.remove(old_file)
                if os.path.exists(old_file + ".sha256"):
                    os.remove(old_file + ".sha256")
                print(f"[PRUNED] Removed old backup: {old_file}")
            except OSError as e:
                print(f"[WARNING] Could not prune {old_file}: {e}")

    return backup_file


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "backups"
    backup_database(out_dir)
