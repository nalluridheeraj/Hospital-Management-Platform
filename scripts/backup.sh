#!/usr/bin/env bash
# ==============================================================================
# Database Backup Wrapper Script
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${1:-backups}"
mkdir -p "$BACKUP_DIR"

echo "Executing automated backup..."
python3 scripts/backup.py "$BACKUP_DIR"

