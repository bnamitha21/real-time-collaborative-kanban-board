$ErrorActionPreference = "Stop"

$ApiBase = if ($env:API_BASE) { $env:API_BASE } else { "http://127.0.0.1:4000/api/v1" }

Write-Host "1. Checking API health..."
$health = Invoke-RestMethod -Uri "$ApiBase/../healthz" -Method Get
Write-Host "API is healthy: $($health.status)"

Write-Host "2. Logging in..."
$loginBody = @{
    email = "admin.hyd@northwind.test"
    password = "Passw0rd!"
} | ConvertTo-Json

$loginRes = Invoke-RestMethod -Uri "$ApiBase/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$token = $loginRes.data.accessToken
Write-Host "Login successful."

Write-Host "3. Fetching workspaces..."
$headers = @{ Authorization = "Bearer $token" }
$workspaces = Invoke-RestMethod -Uri "$ApiBase/me/workspaces" -Method Get -Headers $headers
$tenantId = $workspaces.data[0].tenants[0].id
Write-Host "Tenant ID: $tenantId"

Write-Host "4. Listing boards for tenant..."
$boards = Invoke-RestMethod -Uri "$ApiBase/tenants/$tenantId/boards" -Method Get -Headers $headers
Write-Host "Boards: $($boards | ConvertTo-Json -Depth 3)"
Write-Host "Smoke test complete."
