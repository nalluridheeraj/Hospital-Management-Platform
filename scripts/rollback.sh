#!/usr/bin/env bash
# ==============================================================================
# Automated Container & Deployment Rollback Script
# ==============================================================================
set -euo pipefail

TARGET_TAG="${1:-latest}"
HEALTH_URL="http://localhost:8000/health/readiness"
MAX_ATTEMPTS=15
SLEEP_INTERVAL=2

echo "=========================================================="
echo " Starting Rollback Procedure: Target Tag = ${TARGET_TAG}"
echo "=========================================================="

echo "[1/4] Inspecting current running containers..."
docker compose ps

echo "[2/4] Redeploying web service with target image tag: ${TARGET_TAG}..."
export IMAGE_TAG="${TARGET_TAG}"
docker compose up -d --no-deps web

echo "[3/4] Verifying health and readiness of rolled back service..."
attempt=1
while [ $attempt -le $MAX_ATTEMPTS ]; do
    echo "Health check probe attempt $attempt/$MAX_ATTEMPTS..."
    if curl -s -f "$HEALTH_URL" | grep -q '"status":"ready"'; then
        echo "[4/4] Rollback verified! Service is healthy and serving traffic."
        echo "=========================================================="
        echo " ROLLBACK COMPLETED SUCCESSFULLY "
        echo "=========================================================="
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep $SLEEP_INTERVAL
done

echo "[ERROR] Service failed readiness probe after rollback."
echo "Fetching recent service logs:"
docker compose logs --tail=50 web
exit 1

