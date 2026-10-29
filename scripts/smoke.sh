#!/usr/bin/env bash
set -euo pipefail

# Smoke script: logs in as Hyderabad Tenant Admin and lists boards
API_BASE="${API_BASE:-http://127.0.0.1:4000/api/v1}"

echo "1. Checking API health..."
curl -s -f "${API_BASE}/../healthz" > /dev/null
echo "API is healthy."

echo "2. Logging in..."
LOGIN_RES=$(curl -s -f -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin.hyd@northwind.test", "password": "Passw0rd!"}')

ACCESS_TOKEN=$(echo "${LOGIN_RES}" | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4)
if [ -z "${ACCESS_TOKEN}" ]; then
  echo "Failed to obtain access token." >&2
  exit 1
fi
echo "Login successful."

echo "3. Fetching workspaces..."
WORKSPACES=$(curl -s -f -X GET "${API_BASE}/me/workspaces" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

TENANT_ID=$(echo "${WORKSPACES}" | grep -o '"id":"[^"]*' | head -n 2 | tail -n 1 | cut -d'"' -f4)
echo "Tenant ID: ${TENANT_ID}"

echo "4. Listing boards for tenant..."
BOARDS=$(curl -s -f -X GET "${API_BASE}/tenants/${TENANT_ID}/boards" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

echo "Boards:"
echo "${BOARDS}"
echo "Smoke test complete."

