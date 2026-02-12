param(
  [string]$MMDEPLOY_ROOT = ".\\third_party\\mmdeploy",
  [string]$MODEL = ".\\workspace\\backend\\models\\mmdeploy\\rtmw3d_l_ort\\end2end.onnx",
  [string]$DEPLOY_CFG = "configs/mmpose/pose-detection_simcc_onnxruntime_dynamic.py",
  [int]$WARMUP = 20,
  [int]$NUM_ITERS = 200
)

$profiler = Join-Path $MMDEPLOY_ROOT "tools\profiler.py"
if (-not (Test-Path $profiler)) {
  Write-Host "Missing profiler.py under $MMDEPLOY_ROOT" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path $MODEL)) {
  Write-Host "Missing model: $MODEL" -ForegroundColor Red
  exit 1
}

Write-Host "Running MMDeploy profiler..."
python $profiler `
  (Join-Path $MMDEPLOY_ROOT $DEPLOY_CFG) `
  $MODEL `
  --device cuda `
  --warmup $WARMUP `
  --num-iter $NUM_ITERS
