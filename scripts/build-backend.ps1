Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
Push-Location "$Root"

Write-Host "Triggering robust setup-venv for Backend..." -ForegroundColor Cyan
just setup-venv
Pop-Location
