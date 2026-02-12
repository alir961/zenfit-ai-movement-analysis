Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Building Backend (Dependencies)..." -ForegroundColor Cyan
./scripts/build-backend.ps1

Write-Host "Building Frontend (Production Bundle)..." -ForegroundColor Cyan
./scripts/build-frontend.ps1

Write-Host "Build Complete!" -ForegroundColor Green
