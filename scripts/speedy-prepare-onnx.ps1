param(
    [string]$PythonExe = "speedy_learning/.venv/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $PythonExe)) {
    throw "Python introuvable: $PythonExe"
}

Write-Host "[speedy-onnx] Ensuring third_party/mmpose..." -ForegroundColor Cyan
& ./scripts/speedy-third-party-ensure.ps1
if ($LASTEXITCODE -ne 0) {
    throw "[speedy-onnx] third-party ensure failed with code $LASTEXITCODE"
}

Write-Host "[speedy-onnx] Generating required ONNX models..." -ForegroundColor Cyan
& $PythonExe scripts/speedy-generate-required-onnx.py
if ($LASTEXITCODE -ne 0) {
    throw "[speedy-onnx] ONNX generation failed with code $LASTEXITCODE"
}

$required = @(
    "speedy_learning/models/yolox_s_humanart_fp32.onnx",
    "speedy_learning/models/rtmw3d_l_fp32.onnx"
)

$pathsJson = $required | ConvertTo-Json -Compress
$env:SPEEDY_ONNX_PATHS = $pathsJson
$code = @"
import json
import os
import pathlib
import onnxruntime as ort

paths = json.loads(os.environ['SPEEDY_ONNX_PATHS'])
for p in paths:
    pp = pathlib.Path(p)
    if not pp.exists():
        raise RuntimeError(f'missing model: {pp}')
    sess = ort.InferenceSession(str(pp), providers=['CPUExecutionProvider'])
    print(f'[speedy-onnx] validated {pp.name} inputs={len(sess.get_inputs())} outputs={len(sess.get_outputs())}')
"@
& $PythonExe -c $code
if ($LASTEXITCODE -ne 0) {
    throw "[speedy-onnx] ONNX validation failed with code $LASTEXITCODE"
}
Remove-Item Env:SPEEDY_ONNX_PATHS -ErrorAction SilentlyContinue

Write-Host "[speedy-onnx] Ready. Required ONNX models are present in speedy_learning/models" -ForegroundColor Green
