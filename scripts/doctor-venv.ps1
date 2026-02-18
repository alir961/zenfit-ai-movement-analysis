Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$Py = "$Root/workspace/backend/.venv/Scripts/python.exe"

Write-Host "=== [ZenFit Backend Diagnostic] ==="
Write-Host "Python:     " (& $Py --version)
Write-Host "Pip:        " (& $Py -m pip --version)
Write-Host "Setuptools: " (& $Py -c "import setuptools; print(setuptools.__version__)")
Write-Host "--- Statut Torch / CUDA ---"
& $Py -c "import torch; print(f'Torch: {torch.__version__} | CUDA: {torch.version.cuda} | GPU: {torch.cuda.is_available()}')"
Write-Host "--- Statut OpenMMLab ---"
& $Py -c "import mmcv; import mmengine; print(f'MMCV: {mmcv.__version__} | MMEngine: {mmengine.__version__}')"
& $Py -c "try: import mmpose; print(f'MMPose: {mmpose.__version__}'); except: print('MMPose: Non installe')"
Write-Host "--- Integrite Pip ---"
& $Py -m pip check
Write-Host "===================================="
