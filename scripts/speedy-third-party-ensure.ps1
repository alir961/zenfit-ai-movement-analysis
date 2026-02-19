param(
    [string]$RepoUrl = "https://github.com/open-mmlab/mmpose.git",
    [string]$TargetDir = "third_party/mmpose"
)

$ErrorActionPreference = "Stop"

$target = Resolve-Path -LiteralPath "." | ForEach-Object { Join-Path $_.Path $TargetDir }
$parent = Split-Path -Parent $target
if (!(Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

if (!(Test-Path (Join-Path $target ".git"))) {
    Write-Host "[speedy-third-party] Cloning $RepoUrl -> $TargetDir" -ForegroundColor Cyan
    git clone --depth 1 --branch main $RepoUrl $target
} else {
    Write-Host "[speedy-third-party] Updating existing repo at $TargetDir" -ForegroundColor Cyan
    git -C $target fetch origin main
    git -C $target checkout main
    git -C $target pull --ff-only origin main
}

$sentinels = @(
    (Join-Path $target "projects"),
    (Join-Path $target "mmpose")
)
foreach ($s in $sentinels) {
    if (!(Test-Path $s)) {
        throw "[speedy-third-party] Invalid mmpose checkout, missing sentinel: $s"
    }
}

$head = git -C $target rev-parse --short HEAD
Write-Host "[speedy-third-party] Ready (main @ $head)" -ForegroundColor Green