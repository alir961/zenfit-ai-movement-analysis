# Install the speedy lab dependencies (CUDA 12.1 torch wheels), retrying flaky downloads.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$Py = "$Root/speedy_learning/.venv/Scripts/python.exe"

# chumpy and xtcocotools (mmpose dependencies) are sdists whose setup.py imports
# pip / numpy, so they cannot build in pip's isolated build environment.
& $Py -m pip install numpy==1.26.4 Cython==3.2.4
if ($LASTEXITCODE -ne 0) { throw "numpy/Cython install failed" }
& $Py -m pip install numpy==1.26.4 chumpy==0.70 xtcocotools==1.14.3 --no-build-isolation
if ($LASTEXITCODE -ne 0) { throw "chumpy/xtcocotools install failed" }

for ($i = 1; $i -le 3; $i++) {
  Write-Host "[speedy] pip install attempt $i/3" -ForegroundColor Cyan
  & $Py -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html -r "$Root/speedy_learning/backend/requirements.txt"
  if ($LASTEXITCODE -eq 0) { exit 0 }
  if ($i -lt 3) { Write-Warning "[speedy] pip install failed, retry in 5s..."; Start-Sleep -Seconds 5 }
}
throw "speedy-venv-install failed after 3 attempts"
