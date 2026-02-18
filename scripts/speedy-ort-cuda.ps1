param(
    [string]$PythonExe = "workspace/backend/.venv/Scripts/python.exe",
    [switch]$InstallDeps,
    [switch]$DoctorOnly,
    [string]$RunScript = "speedy_learning/run_dev.py"
)

$ErrorActionPreference = "Stop"

function Assert-Python {
    param([string]$Py)
    if (!(Test-Path $Py)) {
        throw "Python introuvable: $Py"
    }
}

function Install-OrtCudaDeps {
    param([string]$Py)
    & $Py -m pip install --upgrade `
        "onnxruntime-gpu[cuda,cudnn]==1.22.0"
    & $Py -m pip install --upgrade `
        nvidia-cuda-runtime-cu12 `
        nvidia-cublas-cu12 `
        nvidia-cudnn-cu12
}

function Get-NvidiaBinDirsJson {
    param([string]$Py)
    $code = @'
import json
import pathlib
import site

roots = set()
try:
    roots.update(site.getsitepackages())
except Exception:
    pass
try:
    roots.add(site.getusersitepackages())
except Exception:
    pass

dirs = set()
for root in roots:
    if not root:
        continue
    nvidia_root = pathlib.Path(root) / "nvidia"
    if not nvidia_root.exists():
        continue
    for d in nvidia_root.glob("*/bin"):
        if d.is_dir():
            dirs.add(str(d))

    torch_lib = pathlib.Path(root) / "torch" / "lib"
    if torch_lib.is_dir():
        dirs.add(str(torch_lib))

    ort_capi = pathlib.Path(root) / "onnxruntime" / "capi"
    if ort_capi.is_dir():
        dirs.add(str(ort_capi))

print(json.dumps(sorted(dirs)))
'@
    $code | & $Py -
}

function Add-OrtDllDirsToPath {
    param([string[]]$Dirs)
    if (-not $Dirs -or $Dirs.Count -eq 0) {
        Write-Warning "Aucun dossier nvidia/*/bin detecte dans site-packages."
        return
    }

    $current = $env:PATH
    $prefix = ($Dirs -join ";")
    $env:PATH = "$prefix;$current"
    Write-Host "[speedy] PATH DLL ajoute:" -ForegroundColor Cyan
    foreach ($d in $Dirs) {
        Write-Host "  - $d"
    }
}

function Test-OrtCuda {
    param([string]$Py)
    $code = @'
import ctypes
import os
import json
import pathlib
import site

result = {"providers": [], "dll_ok": False, "dll_error": None}
roots = []
try:
    roots.extend(site.getsitepackages())
except Exception:
    pass
try:
    roots.append(site.getusersitepackages())
except Exception:
    pass
for root in roots:
    if not root:
        continue
    r = pathlib.Path(root)
    nvidia = r / "nvidia"
    if nvidia.exists():
        for d in nvidia.glob("*/bin"):
            if d.is_dir():
                try:
                    os.add_dll_directory(str(d))
                except Exception:
                    pass
    for d in (r / "torch" / "lib", r / "onnxruntime" / "capi"):
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
            except Exception:
                pass
try:
    ctypes.CDLL("cudnn64_9.dll")
    result["dll_ok"] = True
except Exception as e:
    result["dll_error"] = str(e)

try:
    import onnxruntime as ort
    result["providers"] = ort.get_available_providers()
except Exception as e:
    result["providers_error"] = str(e)

print(json.dumps(result))
'@
    $code | & $Py -
}

Assert-Python -Py $PythonExe

Write-Host "[speedy] Python executable (venv attendu):" -ForegroundColor Cyan
& $PythonExe -c "import sys; print(sys.executable)"
& $PythonExe -c "import sys; print('prefix=', sys.prefix)"

if ($InstallDeps) {
    Write-Host "[speedy] Installation dependances CUDA/cuDNN Python..." -ForegroundColor Yellow
    Install-OrtCudaDeps -Py $PythonExe
}

$dirsJson = Get-NvidiaBinDirsJson -Py $PythonExe
$dirs = @()
if ($dirsJson) {
    try {
        $parsed = $dirsJson | ConvertFrom-Json
        if ($parsed -is [System.Array]) {
            $dirs = [string[]]$parsed
        } elseif ($parsed) {
            $dirs = @([string]$parsed)
        }
    } catch {
        Write-Warning "Impossible de parser les dossiers CUDA Python: $dirsJson"
    }
}

Add-OrtDllDirsToPath -Dirs $dirs

Write-Host "[speedy] Diagnostic ONNXRuntime/CUDA..." -ForegroundColor Yellow
$diag = Test-OrtCuda -Py $PythonExe
Write-Host $diag

$diagObj = $null
try {
    $diagObj = $diag | ConvertFrom-Json
} catch {
    Write-Warning "Diagnostic JSON non parse, mode CPU force desactive."
}

if ($diagObj -and $diagObj.dll_ok -eq $false) {
    $env:ZENFIT_ORT_CPU_ONLY = "1"
    Write-Warning "cudnn64_9.dll non chargeable. Basculer temporairement en CPU (ZENFIT_ORT_CPU_ONLY=1)."
} else {
    $env:ZENFIT_ORT_CPU_ONLY = "0"
}

if ($DoctorOnly) {
    exit 0
}

Write-Host "[speedy] Launch: $PythonExe $RunScript" -ForegroundColor Green
& $PythonExe $RunScript
