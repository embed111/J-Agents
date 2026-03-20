[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [datetime]$Now = (Get-Date),
    [switch]$DryRun
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

function Test-SectionExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Heading
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    $content = Get-Content -Path $Path -Raw -Encoding UTF8
    return $content -match "(?m)^###\s+$([regex]::Escape($Heading))\s*$"
}

function Get-BulletTexts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }

    $bullets = New-Object System.Collections.Generic.List[string]
    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        if ($line -match '^\s*-\s+(.*\S)\s*$') {
            $bullets.Add($matches[1].Trim())
        }
    }

    return @($bullets | Select-Object -Unique)
}

function Write-ArchiveEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Heading,

        [Parameter(Mandatory = $true)]
        [string[]]$Bullets,

        [switch]$DryRun
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("")
    $lines.Add("### $Heading")
    $lines.Add("")

    foreach ($bullet in $Bullets) {
        $lines.Add("- $bullet")
    }

    $entry = ($lines -join [Environment]::NewLine)
    if ($DryRun) {
        Write-Host "[DRY-RUN] Would append archive section '$Heading' to $Path"
        return
    }

    $content = if (Test-Path -LiteralPath $Path) {
        Get-Content -Path $Path -Raw -Encoding UTF8
    } else {
        ""
    }

    if ($content -match "(?m)^-\s+暂无已完成月份的全局归档条目。\s*$") {
        $content = [regex]::Replace($content, "(?m)^-\s+暂无已完成月份的全局归档条目。\s*(\r?\n)?", "")
        Set-Content -Path $Path -Value $content.TrimEnd() -Encoding UTF8
    }

    Add-Content -Path $Path -Value $entry -Encoding UTF8
}

$workspaceRootPath = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$codexRoot = Join-Path $workspaceRootPath ".codex"
$memoryRoot = Join-Path $codexRoot "memory"

$todayKey = $Now.ToString("yyyy-MM-dd")
$monthKey = $Now.ToString("yyyy-MM")
$yesterday = $Now.AddDays(-1)
$yesterdayKey = $yesterday.ToString("yyyy-MM-dd")
$yesterdayMonthKey = $yesterday.ToString("yyyy-MM")
$previousMonth = $Now.AddMonths(-1)
$previousMonthKey = $previousMonth.ToString("yyyy-MM")

$globalOverviewPath = Join-Path $memoryRoot "全局记忆总览.md"
$yesterdayMonthDir = Join-Path $memoryRoot $yesterdayMonthKey
$yesterdayDailyPath = Join-Path $yesterdayMonthDir ($yesterdayKey + ".md")
$yesterdayMonthOverviewPath = Join-Path $yesterdayMonthDir "记忆总览.md"
$previousMonthDir = Join-Path $memoryRoot $previousMonthKey
$previousMonthOverviewPath = Join-Path $previousMonthDir "记忆总览.md"

$archivedDaily = $false
$archivedMonthly = $false

if (Test-Path -LiteralPath $yesterdayDailyPath) {
    if (Test-SectionExists -Path $yesterdayMonthOverviewPath -Heading $yesterdayKey) {
        Write-Host "[SKIP] Daily memory already archived: $yesterdayKey"
    } else {
        if (-not $DryRun) {
            Ensure-File -Path $yesterdayMonthOverviewPath -Template @"
# $yesterdayMonthKey 记忆总览

## 已归档日期摘要
"@
        }

        $dailyBullets = Get-BulletTexts -Path $yesterdayDailyPath
        if ($dailyBullets.Count -eq 0) {
            $dailyBullets = @("该日记忆文件存在，但未提取到可归档的摘要条目。")
        }

        Write-ArchiveEntry -Path $yesterdayMonthOverviewPath -Heading $yesterdayKey -Bullets $dailyBullets -DryRun:$DryRun
        Write-Host ("[{0}] Archived daily memory to monthly overview: {1}" -f ($(if ($DryRun) { "DRY-RUN" } else { "OK" }), $yesterdayKey))
        $archivedDaily = -not $DryRun
    }
} else {
    Write-Host "[SKIP] No daily memory file to archive for yesterday: $yesterdayKey"
}

if (Test-Path -LiteralPath $previousMonthOverviewPath) {
    if (Test-SectionExists -Path $globalOverviewPath -Heading $previousMonthKey) {
        Write-Host "[SKIP] Monthly overview already archived globally: $previousMonthKey"
    } else {
        if (-not $DryRun) {
            Ensure-File -Path $globalOverviewPath -Template @"
# 全局记忆总览

## 长期稳定记忆

## 跨月归档
"@
        }

        $monthBullets = Get-BulletTexts -Path $previousMonthOverviewPath
        $monthDates = @(
            Get-Content -Path $previousMonthOverviewPath -Encoding UTF8 |
                Where-Object { $_ -match '^###\s+(\d{4}-\d{2}-\d{2})\s*$' } |
                ForEach-Object { $matches[1] }
        )

        $summaryBullets = New-Object System.Collections.Generic.List[string]
        if ($monthDates.Count -gt 0) {
            $summaryBullets.Add("已归档日期：$($monthDates -join '、')")
            $summaryBullets.Add("归档日期数：$($monthDates.Count)")
        }

        foreach ($bullet in ($monthBullets | Select-Object -First 12)) {
            $summaryBullets.Add($bullet)
        }

        if ($summaryBullets.Count -eq 0) {
            $summaryBullets.Add("该月总览文件存在，但未提取到可归档的摘要条目。")
        }

        Write-ArchiveEntry -Path $globalOverviewPath -Heading $previousMonthKey -Bullets @($summaryBullets) -DryRun:$DryRun
        Write-Host ("[{0}] Archived monthly overview to global overview: {1}" -f ($(if ($DryRun) { "DRY-RUN" } else { "OK" }), $previousMonthKey))
        $archivedMonthly = -not $DryRun
    }
} else {
    Write-Host "[SKIP] No previous month overview to archive globally: $previousMonthKey"
}

Write-Host "[SUMMARY] daily_archived=$archivedDaily monthly_archived=$archivedMonthly dry_run=$($DryRun.IsPresent)"
