[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [string]$Summary,
    [string]$Details,
    [datetime]$Now = (Get-Date)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Ensure-File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Template
    )

    $parent = Split-Path -Path $Path -Parent
    if ($parent) {
        Ensure-Directory -Path $parent
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        Set-Content -Path $Path -Value $Template -Encoding UTF8
    }
}

function Add-Bullets {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Lines,

        [string]$Text
    )

    if (-not $Text) {
        return
    }

    $segments = @(
        $Text -split "\r?\n|\s*\|\|\s*" |
            Where-Object { $_ -and $_.Trim() } |
            ForEach-Object { $_.Trim() }
    )

    foreach ($segment in $segments) {
        $Lines.Add("- $segment")
    }
}

$workspaceRootPath = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$codexRoot = Join-Path $workspaceRootPath ".codex"
$memoryRoot = Join-Path $codexRoot "memory"
$monthKey = $Now.ToString("yyyy-MM")
$todayKey = $Now.ToString("yyyy-MM-dd")
$timestamp = $Now.ToString("yyyy-MM-dd HH:mm:ss zzz")
$monthDir = Join-Path $memoryRoot $monthKey
$todayPath = Join-Path $monthDir ($todayKey + ".md")

Ensure-Directory -Path $monthDir
Ensure-File -Path $todayPath -Template @"
# $todayKey 每日记忆

## 工作记录
"@

$hasContent =
    ($Summary -and $Summary.Trim()) -or
    ($Details -and $Details.Trim())

if (-not $hasContent) {
    throw "At least one of Summary or Details must be provided."
}

$entryLines = New-Object System.Collections.Generic.List[string]
$entryLines.Add("")
$entryLines.Add("### [$timestamp]")
$entryLines.Add("")

Add-Bullets -Lines $entryLines -Text $Summary
Add-Bullets -Lines $entryLines -Text $Details

$entry = $entryLines -join [Environment]::NewLine

Add-Content -Path $todayPath -Value $entry -Encoding UTF8
Write-Host "[OK] Appended daily memory: $todayPath"
