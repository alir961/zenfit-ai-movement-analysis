Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$VenvDir = "$Root/workspace/backend/.venv"
$ActivateScript = "$VenvDir/Scripts/Activate.ps1"

Push-Location "$Root/workspace/backend"

# Vérification du venv
if (!(Test-Path $ActivateScript)) {
    Write-Host "Virtual environment not found. Running setup-venv..." -ForegroundColor Yellow
    Pop-Location
    just setup-venv
    Push-Location "$Root/workspace/backend"
}

Write-Host "Activating Virtual Environment..." -ForegroundColor Yellow
# Dot-sourcing du script d'activation pour modifier l'environnement du shell actuel
. $ActivateScript

Write-Host "Starting Backend (RTMW3D) at http://localhost:8001 (auto-reload on app/ changes) ..." -ForegroundColor Cyan
if (-not $env:ZENFIT_RELOAD) { $env:ZENFIT_RELOAD = "1" }
# Maintenant que la session est activée, on peut appeler 'python' directement
python -m app.main

Pop-Location
