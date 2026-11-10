# PowerShell wrapper to generate self-signed TLS certificates
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$CertsDir = Join-Path $ProjectRoot "nginx\certs"

if (-not (Test-Path $CertsDir)) {
    New-Item -ItemType Directory -Path $CertsDir | Out-Null
}

Write-Host "Generating TLS certificates for local reverse proxy..."
python (Join-Path $ProjectRoot "scripts\generate_certs.py") $CertsDir
Write-Host "Certificates ready at $CertsDir" -ForegroundColor Green

