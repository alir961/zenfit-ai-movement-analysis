param(
    [string]$PythonExe = "speedy_learning/.venv/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"

function Assert-Python {
    param([string]$Py)
    if (!(Test-Path $Py)) {
        throw "Python introuvable: $Py"
    }
}

function Ensure-Model {
    param(
        [string]$Name,
        [string]$SpeedyModelsDir,
        [string]$BackendOnnxDir,
        [string]$PythonExe
    )

    $target = Join-Path $SpeedyModelsDir $Name
    if (Test-Path $target) {
        Write-Host "[speedy-onnx] OK (already): $target" -ForegroundColor Green
        return $target
    }

    $backendSrc = Join-Path $BackendOnnxDir $Name
    if (Test-Path $backendSrc) {
        Copy-Item $backendSrc $target -Force
        Write-Host "[speedy-onnx] Copied: $backendSrc -> $target" -ForegroundColor Cyan
        return $target
    }

    Write-Host "[speedy-onnx] Missing $Name in backend cache. Trying artifact preparation..." -ForegroundColor Yellow
    & $PythonExe workspace/backend/scripts/prepare_onnx_artifacts.py --out-dir workspace/backend/models/onnx

    if (Test-Path $backendSrc) {
        Copy-Item $backendSrc $target -Force
        Write-Host "[speedy-onnx] Copied after prepare: $backendSrc -> $target" -ForegroundColor Cyan
        return $target
    }

    throw "Impossible de trouver/generer $Name. Check workspace/backend/models/onnx and export tooling."
}

function Validate-Onnx {
    param([string]$Py, [string[]]$ModelPaths)
    $pathsJson = $ModelPaths | ConvertTo-Json -Compress
    $env:SPEEDY_ONNX_PATHS = $pathsJson
    $code = @'
import json
import os
import pathlib
import onnxruntime as ort

paths = json.loads(os.environ['SPEEDY_ONNX_PATHS'])
for p in paths:
    pp = pathlib.Path(p)
    if not pp.exists():
        raise RuntimeError('missing model: ' + str(pp))
    sess = ort.InferenceSession(str(pp), providers=['CPUExecutionProvider'])
    print('[speedy-onnx] validated {} inputs={} outputs={}'.format(pp.name, len(sess.get_inputs()), len(sess.get_outputs())))
'@
    & $Py -c $code
    Remove-Item Env:SPEEDY_ONNX_PATHS -ErrorAction SilentlyContinue
}

Assert-Python -Py $PythonExe

$speedyModelsDir = "speedy_learning/models"
$backendOnnxDir = "workspace/backend/models/onnx"

if (!(Test-Path $speedyModelsDir)) {
    New-Item -ItemType Directory -Path $speedyModelsDir | Out-Null
}

$required = @(
    "yolox_s_humanart_fp32.onnx",
    "rtmw3d_l_fp32.onnx"
)

$copied = @()
foreach ($name in $required) {
    $copied += Ensure-Model -Name $name -SpeedyModelsDir $speedyModelsDir -BackendOnnxDir $backendOnnxDir -PythonExe $PythonExe
}

Validate-Onnx -Py $PythonExe -ModelPaths $copied

Write-Host "[speedy-onnx] Ready. Required ONNX models are present in $speedyModelsDir" -ForegroundColor Green
