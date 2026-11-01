#!/usr/bin/env python3
"""
setup_portable_postgres.py — Sets up and starts local PostgreSQL without needing Windows admin/UAC elevation.

Steps:
1. Downloads official EnterpriseDB PostgreSQL 16 portable binaries zip
2. Extracts to C:\\Users\\<username>\\.pgsql
3. Initializes database cluster at C:\\Users\\<username>\\.pgsql\\data
4. Starts PostgreSQL server on localhost:5432
5. Runs init_db.py --seed to create the database, roles, RLS policies, and seed data.
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PG_VERSION = "16.6-1"
ZIP_URL = f"https://get.enterprisedb.com/postgresql/postgresql-{PG_VERSION}-windows-x64-binaries.zip"

USER_HOME = Path.home()
PG_BASE_DIR = USER_HOME / ".pgsql"
PG_INSTALL_DIR = PG_BASE_DIR / "pgsql"
PG_BIN_DIR = PG_INSTALL_DIR / "bin"
PG_DATA_DIR = PG_BASE_DIR / "data"
PG_LOG_FILE = PG_BASE_DIR / "server.log"
ZIP_FILE = PG_BASE_DIR / f"postgresql-{PG_VERSION}-binaries.zip"

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(f"[PostgreSQL Setup] {msg}", flush=True)


def download_binaries() -> None:
    PG_BASE_DIR.mkdir(parents=True, exist_ok=True)
    if (PG_BIN_DIR / "postgres.exe").exists():
        log("PostgreSQL binaries already extracted.")
        return

    if not ZIP_FILE.exists():
        log(f"Downloading PostgreSQL {PG_VERSION} portable binaries (~290 MB)...")
        log(f"URL: {ZIP_URL}")
        
        req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(ZIP_FILE, "wb") as out_f:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 1024 * 1024  # 1 MB blocks
            last_report = 0

            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                percent = (downloaded / total_size * 100) if total_size else 0
                if downloaded - last_report >= 20 * 1024 * 1024 or downloaded == total_size:
                    log(f"Downloaded {downloaded // (1024 * 1024)} MB / {total_size // (1024 * 1024)} MB ({percent:.1f}%)")
                    last_report = downloaded

        log("Download complete.")

    log(f"Extracting {ZIP_FILE} to {PG_BASE_DIR}...")
    with zipfile.ZipFile(ZIP_FILE, "r") as z:
        z.extractall(PG_BASE_DIR)
    log("Extraction complete.")


def init_database() -> None:
    if PG_DATA_DIR.exists() and (PG_DATA_DIR / "PG_VERSION").exists():
        log(f"Database cluster already initialized at {PG_DATA_DIR}.")
        return

    log(f"Initializing database cluster at {PG_DATA_DIR}...")
    initdb_exe = PG_BIN_DIR / "initdb.exe"
    cmd = [
        str(initdb_exe),
        "-U", "postgres",
        "-A", "trust",
        "-E", "UTF8",
        "-D", str(PG_DATA_DIR),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"initdb failed: {res.stderr}")
        sys.exit(1)
    log("Database cluster initialized successfully.")


def is_postgres_running() -> bool:
    pg_isready_exe = PG_BIN_DIR / "pg_isready.exe"
    if not pg_isready_exe.exists():
        return False
    res = subprocess.run([str(pg_isready_exe), "-h", "localhost", "-p", "5432"], capture_output=True, text=True)
    return res.returncode == 0


def start_postgres() -> None:
    if is_postgres_running():
        log("PostgreSQL is already running on port 5432.")
        return

    log(f"Starting PostgreSQL server (data dir: {PG_DATA_DIR})...")
    pg_ctl_exe = PG_BIN_DIR / "pg_ctl.exe"
    cmd = [
        str(pg_ctl_exe),
        "-D", str(PG_DATA_DIR),
        "-l", str(PG_LOG_FILE),
        "-o", "-p 5432",
        "start",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"pg_ctl start output: {res.stdout} {res.stderr}")

    # Wait for ready
    log("Waiting for PostgreSQL to accept connections...")
    for _ in range(15):
        if is_postgres_running():
            log("PostgreSQL is ready and accepting connections!")
            return
        time.sleep(1)

    log("PostgreSQL did not become ready in time. Checking logfile:")
    if PG_LOG_FILE.exists():
        print(PG_LOG_FILE.read_text(encoding="utf-8", errors="ignore"))
    sys.exit(1)


def generate_control_scripts() -> None:
    scripts_dir = PROJECT_ROOT / "scripts"
    
    start_script = scripts_dir / "start_db.ps1"
    start_script.write_text(f"""# Start local PostgreSQL
$pgCtl = "{PG_BIN_DIR}\\pg_ctl.exe"
$pgData = "{PG_DATA_DIR}"
$pgLog = "{PG_LOG_FILE}"

Write-Host "Starting local PostgreSQL..." -ForegroundColor Cyan
& $pgCtl -D $pgData -l $pgLog -o "-p 5432" start
& "{PG_BIN_DIR}\\pg_isready.exe" -h localhost -p 5432
""", encoding="utf-8")

    stop_script = scripts_dir / "stop_db.ps1"
    stop_script.write_text(f"""# Stop local PostgreSQL
$pgCtl = "{PG_BIN_DIR}\\pg_ctl.exe"
$pgData = "{PG_DATA_DIR}"

Write-Host "Stopping local PostgreSQL..." -ForegroundColor Yellow
& $pgCtl -D $pgData stop
""", encoding="utf-8")

    status_script = scripts_dir / "status_db.ps1"
    status_script.write_text(f"""# Check local PostgreSQL status
$pgCtl = "{PG_BIN_DIR}\\pg_ctl.exe"
$pgData = "{PG_DATA_DIR}"

& $pgCtl -D $pgData status
& "{PG_BIN_DIR}\\pg_isready.exe" -h localhost -p 5432
""", encoding="utf-8")

    log("Generated helper scripts: scripts/start_db.ps1, scripts/stop_db.ps1, scripts/status_db.ps1")


def run_init_db() -> None:
    log("Running project database initialization (init_db.py --seed)...")
    init_db_script = PROJECT_ROOT / "scripts" / "init_db.py"
    python_exe = sys.executable

    cmd = [
        python_exe,
        str(init_db_script),
        "--pg-user", "postgres",
        "--pg-password", "",
        "--host", "localhost",
        "--port", "5432",
        "--seed",
    ]
    res = subprocess.run(cmd, text=True)
    if res.returncode != 0:
        log("init_db.py failed.")
        sys.exit(1)


def main() -> None:
    print("=" * 60)
    print("  Local Portable PostgreSQL 16 Setup")
    print("=" * 60)
    download_binaries()
    init_database()
    start_postgres()
    generate_control_scripts()
    run_init_db()
    print("=" * 60)
    print("  Local PostgreSQL 16 is RUNNING and configured!")
    print("=" * 60)


if __name__ == "__main__":
    main()

