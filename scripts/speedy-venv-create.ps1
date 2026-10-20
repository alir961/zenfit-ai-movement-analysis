# Create speedy_learning/.venv with a Python supported by torch 2.4.1 (3.10-3.12).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$VenvDir = "$Root/speedy_learning/.venv"

if (!(Test-Path $VenvDir)) {
  $BasePy = $null
  foreach ($v in @("3.12", "3.11", "3.10")) {
    & py "-$v" -c "exit()" 2>$null
    if ($LASTEXITCODE -eq 0) { $BasePy = @("py", "-$v"); break }
  }
  if (-not $BasePy) { throw "Python 3.10-3.12 not found (py launcher). Install Python 3.12." }
  & $BasePy[0] $BasePy[1] -m venv $VenvDir
}
& "$VenvDir/Scripts/python.exe" -m pip install --upgrade pip wheel setuptools==69.5.1
