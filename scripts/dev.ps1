Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Starting ZenFit Development Environment..." -ForegroundColor Cyan

# Start Backend in a separate window
Write-Host "Launching Backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoProfile", "-Command", "just dev-backend"

# Start Frontend in current window (or another one)
Write-Host "Launching Frontend..." -ForegroundColor Yellow
./scripts/dev-frontend.ps1
