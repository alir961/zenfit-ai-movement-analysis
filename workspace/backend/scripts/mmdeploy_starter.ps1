param(
  [string]$MMDEPLOY_ROOT = ".\\third_party\\mmdeploy",
  [string]$MODEL_CFG = ".\\third_party\\mmpose\\projects\\rtmpose3d\\configs\\rtmw3d-l_8xb64_cocktail14-384x288.py",
  [string]$MODEL_CKPT = ".\\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth",
  [string]$DEPLOY_CFG = "configs/mmpose/pose-detection_simcc_onnxruntime_dynamic.py",
  [string]$INPUT = "docs/squat.mp4",
  [string]$WORK_DIR = ".\\workspace\\backend\\models\\mmdeploy\\rtmw3d_l_ort"
)

Write-Host "MMDeploy starter checks..."
if (-not (Test-Path $MMDEPLOY_ROOT)) {
  Write-Host "Missing MMDEPLOY_ROOT: $MMDEPLOY_ROOT" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path $MODEL_CFG)) {
  Write-Host "Missing MODEL_CFG: $MODEL_CFG" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path $MODEL_CKPT)) {
  Write-Host "Missing MODEL_CKPT: $MODEL_CKPT" -ForegroundColor Red
  exit 1
}

New-Item -ItemType Directory -Force -Path $WORK_DIR | Out-Null

$deployPy = Join-Path $MMDEPLOY_ROOT "tools\deploy.py"
if (-not (Test-Path $deployPy)) {
  Write-Host "Missing deploy.py under $MMDEPLOY_ROOT" -ForegroundColor Red
  exit 1
}

Write-Host "Running MMDeploy conversion (starter)..."
python $deployPy `
  (Join-Path $MMDEPLOY_ROOT $DEPLOY_CFG) `
  $MODEL_CFG `
  $MODEL_CKPT `
  $INPUT `
  --work-dir $WORK_DIR `
  --device cuda

Write-Host "Done. Outputs under $WORK_DIR"
