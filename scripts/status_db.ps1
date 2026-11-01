# status_db.ps1 — Checks local PostgreSQL server status
$ErrorActionPreference = "Continue"

$pgBin = "$env:USERPROFILE\.pgsql\pgsql\bin"
$pgData = "$env:USERPROFILE\.pgsql\data"

if (-not (Test-Path "$pgBin\pg_ctl.exe")) {
    Write-Host "[ERROR] PostgreSQL binaries not found at $pgBin" -ForegroundColor Red
    exit 1
}

& "$pgBin\pg_ctl.exe" -D $pgData status
& "$pgBin\pg_isready.exe" -h localhost -p 5432

