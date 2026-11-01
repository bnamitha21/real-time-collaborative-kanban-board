# stop_db.ps1 — Stops the local PostgreSQL database
$ErrorActionPreference = "Stop"

$pgBin = "$env:USERPROFILE\.pgsql\pgsql\bin"
$pgData = "$env:USERPROFILE\.pgsql\data"

if (-not (Test-Path "$pgBin\pg_ctl.exe")) {
    Write-Host "[ERROR] PostgreSQL binaries not found at $pgBin" -ForegroundColor Red
    exit 1
}

Write-Host "Stopping local PostgreSQL server..." -ForegroundColor Yellow
& "$pgBin\pg_ctl.exe" -D $pgData stop
Write-Host "[OK] Local PostgreSQL stopped." -ForegroundColor Green

