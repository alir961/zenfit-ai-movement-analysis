Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
$Py = "$Root/workspace/backend/.venv/Scripts/python.exe"

& $Py -m pip install openmim mmengine
& $Py -m pip install "mmcv>=2.0.1" --no-build-isolation -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html
