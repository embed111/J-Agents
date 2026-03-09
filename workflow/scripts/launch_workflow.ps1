param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8090,
    [string]$RuntimeRoot = ".runtime",
    [switch]$SkipBackfill,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

$target = Join-Path $PSScriptRoot "dev/launch_workflow.ps1"
if (-not (Test-Path $target)) {
    throw "launch script missing: $target"
}

& $target @PSBoundParameters
exit $LASTEXITCODE
