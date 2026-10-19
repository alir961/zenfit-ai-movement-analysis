# Install the speedy lab dependencies (CUDA 12.1 torch wheels), retrying flaky downloads.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$Py = "$Root/speedy_learning/.venv/Scripts/python.exe"

for ($i = 1; $i -le 3; $i++) {
  Write-Host "[speedy] pip install attempt $i/3" -ForegroundColor Cyan
  & $Py -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 -r "$Root/speedy_learning/backend/requirements.txt"
  if ($LASTEXITCODE -eq 0) { exit 0 }
  if ($i -lt 3) { Write-Warning "[speedy] pip install failed, retry in 5s..."; Start-Sleep -Seconds 5 }
}
throw "speedy-venv-install failed after 3 attempts"
