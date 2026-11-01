<#
.SYNOPSIS
    Sets up a local PostgreSQL database for the Kanban Board project.

.DESCRIPTION
    This script:
    1. Installs PostgreSQL 16 locally (via winget) if not already installed
    2. Starts the PostgreSQL service
    3. Runs init_db.py to create roles, database, and apply migrations
    4. Optionally seeds development data

.EXAMPLE
    # First-time setup with seed data:
    .\scripts\setup_db.ps1 -Seed

    # Reset database and re-seed:
    .\scripts\setup_db.ps1 -Seed -Reset

    # Setup without seed data:
    .\scripts\setup_db.ps1

.NOTES
    Run this from the project root directory: c:\Users\Namitha\OneDrive\Desktop\kanban
    Requires Windows with winget available.
    PostgreSQL superuser password will be set to 'postgres' by default.
#>

param(
    [switch]$Seed,
    [switch]$Reset,
    [string]$PgPassword = "postgres",
    [int]$Port = 5432
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host "`n$('='*60)" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "$('='*60)" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  [INFO] $Message" -ForegroundColor Yellow
}

function Find-Psql {
    # Try common PostgreSQL installation paths
    $pgPaths = @(
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\PostgreSQL\14\bin\psql.exe",
        "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    )
    foreach ($path in $pgPaths) {
        if (Test-Path $path) { return $path }
    }
    # Try PATH
    try { return (Get-Command psql -ErrorAction Stop).Source } catch {}
    return $null
}

function Find-PgService {
    # Look for any PostgreSQL service
    try {
        $services = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
        if ($services) { return $services[0] }
    } catch {}
    try {
        $services = Get-Service -Name "postgres*" -ErrorAction SilentlyContinue
        if ($services) { return $services[0] }
    } catch {}
    return $null
}

function Get-PgBinDir {
    $pgPaths = @(
        "C:\Program Files\PostgreSQL\16\bin",
        "C:\Program Files\PostgreSQL\17\bin",
        "C:\Program Files\PostgreSQL\15\bin",
        "C:\Program Files\PostgreSQL\14\bin",
    )
    foreach ($p in $pgPaths) {
        if (Test-Path "$p\psql.exe") { return $p }
    }
    return $null
}

# ---- Banner ----
Write-Host "`n$('='*60)" -ForegroundColor Magenta
Write-Host "  Kanban Board - Local PostgreSQL Setup Script" -ForegroundColor Magenta
Write-Host "$('='*60)" -ForegroundColor Magenta
Write-Host "  Project root: $ProjectRoot"
Write-Host "  Port:         $Port"
Write-Host "  Seed data:    $Seed"
Write-Host "  Reset DB:     $Reset"
Write-Host ""

Set-Location $ProjectRoot

# ---- Step 1: Check / Install PostgreSQL ----
Write-Step "Checking PostgreSQL installation..."

$psqlPath = Find-Psql
if ($psqlPath) {
    Write-OK "PostgreSQL found at: $psqlPath"
} else {
    Write-Info "PostgreSQL not found. Attempting to install via winget..."
    try {
        winget install --id PostgreSQL.PostgreSQL.16 --silent --accept-source-agreements --accept-package-agreements
        Write-OK "PostgreSQL installed successfully."
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        $psqlPath = Find-Psql
        if (-not $psqlPath) {
            Write-Host "  [WARN] psql not found in PATH after install. You may need to restart your terminal." -ForegroundColor Yellow
            Write-Host "  After restarting, re-run this script." -ForegroundColor Yellow
            exit 0
        }
    } catch {
        Write-Host "`n  PostgreSQL installation via winget failed." -ForegroundColor Red
        Write-Host "  Please install PostgreSQL manually from: https://www.postgresql.org/download/windows/" -ForegroundColor Red
        Write-Host "  Then re-run this script." -ForegroundColor Red
        Write-Host ""
        Write-Host "  Manual install notes:" -ForegroundColor Yellow
        Write-Host "    - Download: https://www.enterprisedb.com/downloads/postgres-postgresql-installers" -ForegroundColor Yellow
        Write-Host "    - Set superuser password to: postgres" -ForegroundColor Yellow
        Write-Host "    - Keep default port: 5432" -ForegroundColor Yellow
        Write-Host "    - After install, re-run: .\scripts\setup_db.ps1 -Seed" -ForegroundColor Yellow
        exit 1
    }
}

# ---- Step 2: Ensure PostgreSQL service is running ----
Write-Step "Ensuring PostgreSQL service is running..."

$pgBinDir = Get-PgBinDir
if ($pgBinDir) {
    $env:PATH = "$pgBinDir;$env:PATH"
}

$pgService = Find-PgService
if ($pgService) {
    if ($pgService.Status -ne "Running") {
        Write-Info "Starting PostgreSQL service '$($pgService.Name)'..."
        try {
            Start-Service -Name $pgService.Name
            Start-Sleep -Seconds 3
            Write-OK "PostgreSQL service started."
        } catch {
            Write-Host "  Could not start service automatically. Please start it manually." -ForegroundColor Red
            Write-Host "  Run: Start-Service -Name '$($pgService.Name)'" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-OK "PostgreSQL service '$($pgService.Name)' is already running."
    }
} else {
    Write-Info "No PostgreSQL Windows service found."
    Write-Info "Assuming PostgreSQL is running (e.g., started manually or via pg_ctl)."
}

# ---- Step 3: Test connectivity ----
Write-Step "Testing PostgreSQL connectivity on port $Port..."

$env:PGPASSWORD = $PgPassword
$env:PGHOST = "localhost"
$env:PGPORT = "$Port"

$maxRetries = 10
$retryCount = 0
$connected = $false

while ($retryCount -lt $maxRetries -and -not $connected) {
    try {
        $result = & psql -U postgres -c "SELECT 1;" 2>&1
        if ($LASTEXITCODE -eq 0) {
            $connected = $true
            Write-OK "Connected to PostgreSQL successfully."
        }
    } catch {}
    if (-not $connected) {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Info "Waiting for PostgreSQL to start ($retryCount/$maxRetries)..."
            Start-Sleep -Seconds 2
        }
    }
}

if (-not $connected) {
    Write-Host "`n  Could not connect to PostgreSQL on localhost:$Port" -ForegroundColor Red
    Write-Host "  Please ensure PostgreSQL is running and accessible." -ForegroundColor Red
    Write-Host "  Default superuser: postgres / $PgPassword" -ForegroundColor Yellow
    exit 1
}

# ---- Step 4: Run Python init_db.py ----
Write-Step "Running database initialization script..."

# Find Python executable in venv
$pythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    # Try system python
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue)?.Source
    if (-not $pythonExe) {
        Write-Host "  Python not found. Please activate the virtual environment first:" -ForegroundColor Red
        Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
        exit 1
    }
    Write-Info "Using system Python: $pythonExe"
} else {
    Write-OK "Using venv Python: $pythonExe"
}

$initArgs = @(
    "$ProjectRoot\scripts\init_db.py",
    "--pg-user", "postgres",
    "--pg-password", $PgPassword,
    "--host", "localhost",
    "--port", "$Port"
)

if ($Seed) { $initArgs += "--seed" }
if ($Reset) { $initArgs += "--reset" }

$env:PGPASSWORD = $PgPassword

Write-Info "Executing: python scripts/init_db.py $($initArgs[1..$initArgs.Length] -join ' ')"
& $pythonExe @initArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n  Database initialization failed!" -ForegroundColor Red
    exit 1
}

# ---- Step 5: Verify .env file ----
Write-Step "Checking .env configuration..."

$envFile = "$ProjectRoot\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    $hasOwnerUrl = $envContent -match "DATABASE_URL_OWNER=postgresql://owner:owner_pw@localhost:$Port/kanban"
    $hasAppUrl   = $envContent -match "DATABASE_URL=postgresql://kanban_app:app_pw@localhost:$Port/kanban"

    if ($hasOwnerUrl -and $hasAppUrl) {
        Write-OK ".env is correctly configured with local PostgreSQL URLs."
    } else {
        Write-Info ".env may need updating. Expected values:"
        Write-Host "    DATABASE_URL_OWNER=postgresql://owner:owner_pw@localhost:$Port/kanban" -ForegroundColor Yellow
        Write-Host "    DATABASE_URL=postgresql://kanban_app:app_pw@localhost:$Port/kanban" -ForegroundColor Yellow
    }
} else {
    Write-Info ".env file not found. Creating from .env.example..."
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env" -ErrorAction SilentlyContinue
    Write-OK ".env created from .env.example. Please review and update if needed."
}

# ---- Done ----
Write-Host "`n$('='*60)" -ForegroundColor Green
Write-Host "  Database setup complete!" -ForegroundColor Green
Write-Host "$('='*60)" -ForegroundColor Green
Write-Host ""
Write-Host "  Connection details:" -ForegroundColor White
Write-Host "    Owner (migrations): postgresql://owner:owner_pw@localhost:$Port/kanban" -ForegroundColor Gray
Write-Host "    App (with RLS):     postgresql://kanban_app:app_pw@localhost:$Port/kanban" -ForegroundColor Gray
Write-Host ""
Write-Host "  To start the backend server:" -ForegroundColor White
Write-Host "    .\.venv\Scripts\python -m server.src.main" -ForegroundColor Gray
Write-Host ""
Write-Host "  To start the frontend:" -ForegroundColor White
Write-Host "    cd client; npm run dev" -ForegroundColor Gray
Write-Host ""
if ($Seed) {
    Write-Host "  Test credentials (all passwords: Passw0rd!):" -ForegroundColor White
    Write-Host "    orgadmin@northwind.test  — Org Admin, Northwind Traders" -ForegroundColor Gray
    Write-Host "    admin.hyd@northwind.test — Tenant Admin, Hyderabad branch" -ForegroundColor Gray
    Write-Host "    member.hyd@northwind.test — Member, Hyderabad branch" -ForegroundColor Gray
    Write-Host ""
}

