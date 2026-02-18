Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$VenvDir = "$Root/workspace/backend/.venv"
$Py = "$VenvDir/Scripts/python.exe"

Write-Host "--- [1/6] Initialisation du venv dans $VenvDir ---"
if (!(Test-Path $VenvDir)) { python -m venv $VenvDir }

Write-Host "--- [2/6] Mise a jour des outils de packaging (pin setuptools 69.5.1) ---"
& $Py -m pip install --upgrade pip wheel "setuptools==69.5.1" packaging

Write-Host "--- [3/6] Verification/Installation de la stack Torch/CUDA ---"
& $Py -m pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
& $Py -c "import torch; print(f'Torch {torch.__version__} valide (CUDA: {torch.version.cuda})')"

Write-Host "--- [4/6] Installation de OpenMMLab (MIM, MMEngine, MMCV) ---"
& $Py -m pip install openmim mmengine
& $Py -m pip install "mmcv>=2.0.1" --no-build-isolation -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html

Write-Host "--- [5/6] Installation des requirements projet ---"
if (Test-Path "$Root/workspace/backend/requirements.txt") {
  & $Py -m pip install -r "$Root/workspace/backend/requirements.txt"
}

Write-Host "--- [6/6] Verifications finales ---"
& "$PSScriptRoot/doctor-venv.ps1"
