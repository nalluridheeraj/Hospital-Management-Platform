#!/usr/bin/env bash
# ==============================================================================
# Database Restore Wrapper Script
# ==============================================================================
set -euo pipefail

BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    echo "No backup file specified. Searching for latest backup in backups/..."
    BACKUP_FILE=$(find backups -type f -name "*.gz" | sort | tail -n 1)
    if [ -z "$BACKUP_FILE" ]; then
        echo "Error: No backup files found in backups/ directory."
        exit 1
    fi
    echo "Using latest backup: $BACKUP_FILE"
fi

echo "Initiating database restore from: $BACKUP_FILE"
python3 scripts/restore.py "$BACKUP_FILE"

