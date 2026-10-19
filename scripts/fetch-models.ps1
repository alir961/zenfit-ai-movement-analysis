# Fetch what the workspace backend loads at startup: the MMPose sources
# (RTMPose3D config) under third_party/ and the RTMW3D-L checkpoint at the repo root.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
Push-Location $Root
try {
  & "$PSScriptRoot/speedy-third-party-ensure.ps1"

  $Ckpt = "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"
  $Url = "https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/$Ckpt"
  if (Test-Path $Ckpt) {
    Write-Host "[fetch-models] $Ckpt already present"
  } else {
    Write-Host "[fetch-models] Downloading $Ckpt"
    Invoke-WebRequest -Uri $Url -OutFile "$Ckpt.part"
    Move-Item "$Ckpt.part" $Ckpt
  }
} finally {
  Pop-Location
}
