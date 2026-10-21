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
  # The checkpoint is a pickle, which can run code when loaded: only keep the known file.
  $Sha256 = "794dbc78b04a43d81781f8ab0eba5b24f3dd5d71aaf6ae253940424159fb81ed"
  if (Test-Path $Ckpt) {
    if ((Get-FileHash -Algorithm SHA256 $Ckpt).Hash -ne $Sha256) {
      throw "[fetch-models] $Ckpt does not match the expected SHA-256; delete it and run again"
    }
    Write-Host "[fetch-models] $Ckpt already present (checksum OK)"
  } else {
    Write-Host "[fetch-models] Downloading $Ckpt"
    Invoke-WebRequest -Uri $Url -OutFile "$Ckpt.part"
    if ((Get-FileHash -Algorithm SHA256 "$Ckpt.part").Hash -ne $Sha256) {
      Remove-Item "$Ckpt.part"
      throw "[fetch-models] Downloaded file does not match the expected SHA-256"
    }
    Move-Item "$Ckpt.part" $Ckpt
  }
} finally {
  Pop-Location
}
