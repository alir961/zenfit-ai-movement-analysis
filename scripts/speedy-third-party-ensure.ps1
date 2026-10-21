param(
    [string]$RepoUrl = "https://github.com/open-mmlab/mmpose.git",
    [string]$TargetDir = "third_party/mmpose",
    # Pinned MMPose commit: its config is executed and its code imported at startup,
    # so the checkout must not follow whatever is pushed to main.
    [string]$Commit = $(if ($env:MMPOSE_COMMIT) { $env:MMPOSE_COMMIT } else { "759b39c13fea6ba094afc1fa932f51dc1b11cbf9" })
)

$ErrorActionPreference = "Stop"

$target = Resolve-Path -LiteralPath "." | ForEach-Object { Join-Path $_.Path $TargetDir }
$parent = Split-Path -Parent $target
if (!(Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

if (!(Test-Path (Join-Path $target ".git"))) {
    Write-Host "[speedy-third-party] Cloning $RepoUrl @ $Commit -> $TargetDir" -ForegroundColor Cyan
    git init -q $target
    git -C $target remote add origin $RepoUrl
}
$head = git -C $target rev-parse -q --verify HEAD 2>$null
if ($head -ne $Commit) {
    Write-Host "[speedy-third-party] Checking out $Commit in $TargetDir" -ForegroundColor Cyan
    git -C $target fetch -q --depth 1 origin $Commit
    if ($LASTEXITCODE -ne 0) { throw "[speedy-third-party] git fetch failed" }
    git -C $target checkout -q --detach $Commit
    if ($LASTEXITCODE -ne 0) { throw "[speedy-third-party] git checkout failed" }
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

Write-Host "[speedy-third-party] Ready (mmpose @ $($Commit.Substring(0, 12)))" -ForegroundColor Green
