[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
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

$workspaceRootPath = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$codexRoot = Join-Path $workspaceRootPath ".codex"
$memoryRoot = Join-Path $codexRoot "memory"
$monthKey = $Now.ToString("yyyy-MM")
$todayKey = $Now.ToString("yyyy-MM-dd")
$yesterdayKey = $Now.AddDays(-1).ToString("yyyy-MM-dd")
$previousMonthKey = $Now.AddMonths(-1).ToString("yyyy-MM")

$globalOverviewPath = Join-Path $memoryRoot "全局记忆总览.md"
$monthDir = Join-Path $memoryRoot $monthKey
$monthOverviewPath = Join-Path $monthDir "记忆总览.md"
$todayPath = Join-Path $monthDir ($todayKey + ".md")
$yesterdayMonthDir = Join-Path $memoryRoot ($Now.AddDays(-1).ToString("yyyy-MM"))
$yesterdayPath = Join-Path $yesterdayMonthDir ($yesterdayKey + ".md")
$previousMonthDir = Join-Path $memoryRoot $previousMonthKey
$previousMonthOverviewPath = Join-Path $previousMonthDir "记忆总览.md"

Ensure-Directory -Path $memoryRoot
Ensure-Directory -Path $monthDir

Ensure-File -Path $globalOverviewPath -Template @"
# 全局记忆总览

## 长期稳定记忆

## 跨月归档
"@

Ensure-File -Path $monthOverviewPath -Template @"
# $monthKey 记忆总览

## 已归档日期摘要
"@

Ensure-File -Path $todayPath -Template @"
# $todayKey 每日记忆

## 工作记录
"@

$warnings = New-Object System.Collections.Generic.List[string]
$monthOverviewContent = Get-Content -Path $monthOverviewPath -Raw -Encoding UTF8
$globalOverviewContent = Get-Content -Path $globalOverviewPath -Raw -Encoding UTF8

if (Test-Path -LiteralPath $yesterdayPath) {
    if ($monthOverviewContent -notmatch [regex]::Escape($yesterdayKey)) {
        $warnings.Add("昨日记忆尚未归档到月度总览: $yesterdayKey")
    }
}

if (Test-Path -LiteralPath $previousMonthOverviewPath) {
    if ($globalOverviewContent -notmatch [regex]::Escape($previousMonthKey)) {
        $warnings.Add("上月总览尚未归档到全局总览: $previousMonthKey")
    }
}

Write-Host "[READ] $(Join-Path $codexRoot 'MEMORY.md')"
Write-Host "[READ] $globalOverviewPath"
Write-Host "[READ] $monthOverviewPath"
Write-Host "[READ] $todayPath"

if ($warnings.Count -eq 0) {
    Write-Host "[OK] Memory context is ready."
    exit 0
}

foreach ($warning in $warnings) {
    Write-Host "[WARN] $warning"
}

exit 0
