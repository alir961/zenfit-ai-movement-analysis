Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/.."
Push-Location "$Root/workspace/frontend"
bun run build
Pop-Location
