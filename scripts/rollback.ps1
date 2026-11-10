# ==============================================================================
# PowerShell Automated Container & Deployment Rollback Script
# ==============================================================================
param (
    [string]$TargetTag = "latest"
)

$ErrorActionPreference = "Stop"
$HealthUrl = "http://localhost:8000/health/readiness"
$MaxAttempts = 15
$SleepInterval = 2

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting Rollback Procedure: Target Tag = $TargetTag" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "[1/4] Inspecting current running containers..."
docker compose ps

Write-Host "[2/4] Redeploying web service with target image tag: $TargetTag..."
$env:IMAGE_TAG = $TargetTag
docker compose up -d --no-deps web

Write-Host "[3/4] Verifying health and readiness of rolled back service..."
$healthy = $false
for ($i = 1; $i -le $MaxAttempts; $i++) {
    Write-Host "Health check probe attempt $i/$MaxAttempts..."
    try {
        $resp = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($resp -and $resp.status -eq "ready") {
            $healthy = $true
            break
        }
    } catch {
        # Retry on connection failure
    }
    Start-Sleep -Seconds $SleepInterval
}

if ($healthy) {
    Write-Host "[4/4] Rollback verified! Service is healthy and serving traffic." -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " ROLLBACK COMPLETED SUCCESSFULLY " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[ERROR] Service failed readiness probe after rollback." -ForegroundColor Red
    Write-Host "Fetching recent service logs:" -ForegroundColor Yellow
    docker compose logs --tail=50 web
    exit 1
}
