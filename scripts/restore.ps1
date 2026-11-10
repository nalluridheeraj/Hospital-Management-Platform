# ==============================================================================
# PowerShell Automated Database Restore Script
# ==============================================================================
param (
    [string]$BackupFile = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($BackupFile)) {
    Write-Host "No backup file specified. Locating latest backup in backups\..." -ForegroundColor Yellow
    $BackupDir = Join-Path $ProjectRoot "backups"
    if (Test-Path $BackupDir) {
        $latest = Get-ChildItem -Path $BackupDir -Filter "*.gz" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latest) {
            $BackupFile = $latest.FullName
            Write-Host "Using latest backup: $BackupFile" -ForegroundColor Cyan
        }
    }
}

if ([string]::IsNullOrWhiteSpace($BackupFile) -or -not (Test-Path $BackupFile)) {
    Write-Host "Error: Backup file '$BackupFile' does not exist." -ForegroundColor Red
    exit 1
}

Write-Host "Executing database restore from: $BackupFile" -ForegroundColor Cyan
python (Join-Path $ProjectRoot "scripts\restore.py") $BackupFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database restore and health check completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Database restore failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

