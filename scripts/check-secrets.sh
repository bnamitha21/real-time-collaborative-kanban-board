#!/usr/bin/env bash
set -euo pipefail

echo "=== Running Secrets & Credentials Scan ==="

FAILED=0

# 1. Check for tracked .env files
echo "[1/3] Checking for tracked .env files..."
TRACKED_ENV=$(git ls-files | grep -E '\.env(\..+)?$' | grep -v '\.example' || true)
if [ -n "$TRACKED_ENV" ]; then
    echo "ERROR: Tracked .env files found:"
    echo "$TRACKED_ENV"
    FAILED=1
else
    echo "OK: No tracked .env files."
fi

# 2. Check for private keys
echo "[2/3] Checking for private keys in repository..."
if git grep -E -I "-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----" -- ':!scripts/check-secrets.sh' >/dev/null 2>&1; then
    echo "ERROR: Found private key markers in tracked files!"
    git grep -E -n -I "-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----" -- ':!scripts/check-secrets.sh'
    FAILED=1
else
    echo "OK: No private keys found."
fi

# 3. Check for obvious AWS access key patterns
echo "[3/3] Checking for cloud provider secrets..."
if git grep -E -I "AKIA[0-9A-Z]{16}" >/dev/null 2>&1; then
    echo "ERROR: Potential AWS Access Key ID detected!"
    FAILED=1
else
    echo "OK: No cloud API keys found."
fi

if [ $FAILED -ne 0 ]; then
    echo "Secrets scan FAILED."
    exit 1
fi

echo "=== Secrets & Credentials Scan PASSED ==="
exit 0

