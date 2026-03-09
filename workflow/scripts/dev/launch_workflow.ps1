param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8090,
    [string]$RuntimeRoot = ".runtime",
    [switch]$SkipBackfill,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $root
$runtimeRootPath = if ([System.IO.Path]::IsPathRooted($RuntimeRoot)) {
    [System.IO.Path]::GetFullPath($RuntimeRoot)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $root $RuntimeRoot))
}
New-Item -ItemType Directory -Path $runtimeRootPath -Force | Out-Null
$entryScriptPath = (Join-Path $root "scripts/bin/workflow_entry_cli.py")

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    throw "python not found in PATH."
}

Write-Host "[workflow] workspace: $root"
Write-Host "[workflow] runtime root: $runtimeRootPath"
Write-Host "[workflow] python: $($pythonCmd.Source)"

if (-not $SkipBackfill) {
    Write-Host "[workflow] backfill JSONL -> SQLite ..."
    & python scripts/bin/workflow_entry_cli.py --root $runtimeRootPath --mode backfill
    if ($LASTEXITCODE -ne 0) {
        throw "backfill failed with exit code $LASTEXITCODE"
    }
}
else {
    Write-Host "[workflow] skip backfill."
}

Write-Host "[workflow] refresh status ..."
& python scripts/bin/workflow_entry_cli.py --root $runtimeRootPath --mode status
if ($LASTEXITCODE -ne 0) {
    throw "status failed with exit code $LASTEXITCODE"
}

$url = "http://$BindHost`:$Port"
if ($OpenBrowser) {
    Start-Process $url | Out-Null
}

Write-Host "[workflow] web => $url"
Write-Host "[workflow] press Ctrl+C to stop."
& python scripts/bin/workflow_web_server.py --root $runtimeRootPath --entry-script $entryScriptPath --host $BindHost --port $Port --focus "Phase0: web 对话 + 训练工作流"
if ($LASTEXITCODE -ne 0) {
    throw "web server exited with code $LASTEXITCODE"
}
