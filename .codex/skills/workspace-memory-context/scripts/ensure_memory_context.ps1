[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [datetime]$Now = (Get-Date)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRootPath = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$delegateScriptPath = Join-Path $workspaceRootPath ".codex\scripts\ensure_memory_context.ps1"

if (-not (Test-Path -LiteralPath $delegateScriptPath)) {
    throw "Missing delegate script: $delegateScriptPath"
}

& $delegateScriptPath -WorkspaceRoot $workspaceRootPath -Now $Now
if (Test-Path variable:LASTEXITCODE) {
    exit $LASTEXITCODE
}

exit 0
