# start_db.ps1 — Starts the local PostgreSQL database
$ErrorActionPreference = "Stop"

$pgBin = "$env:USERPROFILE\.pgsql\pgsql\bin"
$pgData = "$env:USERPROFILE\.pgsql\data"
$pgLog = "$env:USERPROFILE\.pgsql\server.log"

if (-not (Test-Path "$pgBin\pg_ctl.exe")) {
    Write-Host "[ERROR] PostgreSQL binaries not found at $pgBin" -ForegroundColor Red
    exit 1
}

Write-Host "Starting local PostgreSQL server..." -ForegroundColor Cyan
& "$pgBin\pg_ctl.exe" -D $pgData -l $pgLog -o "-p 5432" start
Start-Sleep -Seconds 2
& "$pgBin\pg_isready.exe" -h localhost -p 5432
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Local PostgreSQL is running on port 5432." -ForegroundColor Green
} else {
    Write-Host "[WARN] Could not connect to PostgreSQL. Check log at $pgLog" -ForegroundColor Yellow
}

