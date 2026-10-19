Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
Push-Location "$Root/workspace/frontend"
bun run typecheck
bun run test
Pop-Location

$BackendPy = "$Root/workspace/backend/.venv/Scripts/python.exe"
if (Test-Path $BackendPy) {
  Push-Location "$Root/workspace/backend"
  & $BackendPy -m pytest -q tests
  Pop-Location
} else {
  Write-Host "Backend venv missing, skipping backend tests (run: just setup-venv)"
}
