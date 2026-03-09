param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir,
    [string]$GuideFileName = "目录导读.md",
    [string]$ArchiveDir = "logs/archive",
    [int]$LineThreshold = 800,
    [int]$SizeKbThreshold = 120,
    [int]$IdleDays = 14,
    [int]$KeepTailLines = 300,
    [string[]]$ArchiveFiles = @(),
    [string[]]$ExcludePathPatterns = @(
        "logs/session-history/*",
        "logs/change-log-history/*",
        "logs/archive/*",
        "*/archive/*"
    ),
    [switch]$AutoArchive,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-TargetPath {
    param(
        [string]$RepoRoot,
        [string]$Target
    )
    if ([IO.Path]::IsPathRooted($Target)) {
        return (Resolve-Path $Target).Path
    }
    return (Resolve-Path (Join-Path $RepoRoot $Target)).Path
}

function Get-RelativePath {
    param(
        [string]$BasePath,
        [string]$FullPath
    )
    $base = $BasePath.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    return $FullPath -replace ("^" + [regex]::Escape($base)), ""
}

function Get-LineCountSafe {
    param([string]$Path)
    try {
        return (Get-Content -Path $Path | Measure-Object -Line).Lines
    }
    catch {
        return -1
    }
}

function Test-IsExcludedPath {
    param(
        [string]$RelativePath,
        [string[]]$Patterns
    )
    $p1 = $RelativePath -replace "\\", "/"
    foreach ($pattern in $Patterns) {
        $norm = $pattern -replace "\\", "/"
        if ($p1 -like $norm) {
            return $true
        }
    }
    return $false
}

function Ensure-ArchiveIndex {
    param([string]$IndexPath)
    if (-not (Test-Path $IndexPath)) {
        $body = @(
            "# Archive Index",
            "",
            "- Policy: archive by moving older lines and keeping source readable.",
            ""
        )
        Set-Content -Path $IndexPath -Value $body -Encoding UTF8
    }
}

function Archive-ByTail {
    param(
        [string]$TargetRoot,
        [string]$RelativePath,
        [string]$ArchiveDir,
        [int]$KeepTailLines,
        [switch]$DryRun
    )
    $sourcePath = Join-Path $TargetRoot $RelativePath
    if (-not (Test-Path $sourcePath)) {
        throw "Missing archive source: $sourcePath"
    }

    $lines = Get-Content -Path $sourcePath
    if ($lines.Count -le $KeepTailLines) {
        return [PSCustomObject]@{
            file = $RelativePath
            changed = $false
            moved = 0
            reason = "line_count_not_exceed_keep_tail"
            archive = "-"
        }
    }

    $movedCount = $lines.Count - $KeepTailLines
    $movedLines = @($lines[0..($movedCount - 1)])
    $keptLines = @($lines[$movedCount..($lines.Count - 1)])

    $archiveRoot = Join-Path $TargetRoot $ArchiveDir
    $safeRel = $RelativePath -replace '[\\/:\*\?"<>\|]', "__"
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $archiveName = "$safeRel-history-$stamp.md"
    $archivePath = Join-Path $archiveRoot $archiveName
    $indexPath = Join-Path $archiveRoot "archive-index.md"

    $archiveBody = New-Object System.Collections.Generic.List[string]
    $archiveBody.Add("# File Archive")
    $archiveBody.Add("")
    $archiveBody.Add("- Time: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))")
    $archiveBody.Add("- Source: $RelativePath")
    $archiveBody.Add("- Moved lines: $movedCount")
    $archiveBody.Add("")
    foreach ($line in $movedLines) {
        $archiveBody.Add([string]$line)
    }

    if ($DryRun) {
        return [PSCustomObject]@{
            file = $RelativePath
            changed = $true
            moved = $movedCount
            reason = "dry_run"
            archive = (Get-RelativePath -BasePath $TargetRoot -FullPath $archivePath)
        }
    }

    if (-not (Test-Path $archiveRoot)) {
        New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
    }

    Set-Content -Path $archivePath -Value $archiveBody -Encoding UTF8
    Set-Content -Path $sourcePath -Value $keptLines -Encoding UTF8
    Ensure-ArchiveIndex -IndexPath $indexPath

    $archiveRel = Get-RelativePath -BasePath $TargetRoot -FullPath $archivePath
    $indexLine = "1. $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) | source=$RelativePath | moved=$movedCount | archive=$archiveRel"
    Add-Content -Path $indexPath -Value $indexLine -Encoding UTF8

    return [PSCustomObject]@{
        file = $RelativePath
        changed = $true
        moved = $movedCount
        reason = "archived"
        archive = $archiveRel
    }
}

$repoRoot = Get-RepoRoot
$targetPath = Resolve-TargetPath -RepoRoot $repoRoot -Target $TargetDir

if (-not (Test-Path $targetPath -PathType Container)) {
    throw "Target directory not found: $targetPath"
}

$topLevelFiles = Get-ChildItem -Path $targetPath -File
$topLevelCompliant = ($topLevelFiles.Count -eq 1 -and $topLevelFiles[0].Name -eq $GuideFileName)

Write-Host "TARGET: $targetPath"
Write-Host "TOP_LEVEL_FILES: $($topLevelFiles.Count)"
Write-Host "TOP_LEVEL_SINGLE_GUIDE: $topLevelCompliant"
if (-not $topLevelCompliant -and $topLevelFiles.Count -gt 0) {
    Write-Host ("TOP_LEVEL_LIST: " + (($topLevelFiles | ForEach-Object { $_.Name }) -join ", "))
}

$archiveRootForFilter = Join-Path $targetPath $ArchiveDir
$allFiles = Get-ChildItem -Path $targetPath -Recurse -File

$report = New-Object System.Collections.Generic.List[object]
foreach ($file in $allFiles) {
    $relative = Get-RelativePath -BasePath $targetPath -FullPath $file.FullName

    if ($relative -eq $GuideFileName) {
        continue
    }
    if ($archiveRootForFilter -and $file.FullName.StartsWith($archiveRootForFilter, [System.StringComparison]::OrdinalIgnoreCase)) {
        continue
    }
    if (Test-IsExcludedPath -RelativePath $relative -Patterns $ExcludePathPatterns) {
        continue
    }

    $lineCount = Get-LineCountSafe -Path $file.FullName
    $sizeKb = [math]::Round(($file.Length / 1KB), 2)
    $daysSinceUpdate = [math]::Floor(((Get-Date) - $file.LastWriteTime).TotalDays)

    $reasons = New-Object System.Collections.Generic.List[string]
    if ($lineCount -ge 0 -and $lineCount -ge $LineThreshold) {
        $reasons.Add("line_count($lineCount) >= $LineThreshold")
    }
    if ($sizeKb -ge $SizeKbThreshold) {
        $reasons.Add("size_kb($sizeKb) >= $SizeKbThreshold")
    }
    if ($IdleDays -gt 0 -and $daysSinceUpdate -ge $IdleDays) {
        $reasons.Add("days_since_update($daysSinceUpdate) >= $IdleDays")
    }

    $report.Add([PSCustomObject]@{
            file = $relative
            lines = $lineCount
            size_kb = $sizeKb
            days_since_update = $daysSinceUpdate
            triggered = ($reasons.Count -gt 0)
            reasons = if ($reasons.Count -eq 0) { "-" } else { ($reasons -join "; ") }
        })
}

$report |
Sort-Object -Property @{ Expression = "triggered"; Descending = $true }, @{ Expression = "size_kb"; Descending = $true } |
Format-Table -AutoSize

$triggered = @($report | Where-Object { $_.triggered })
Write-Host "TRIGGER_COUNT: $($triggered.Count)"

if (-not $AutoArchive) {
    Write-Host "CHECK_ONLY: pass -AutoArchive with -ArchiveFiles to archive selected files."
    exit 0
}

if ($ArchiveFiles.Count -eq 0) {
    Write-Host "AUTOARCHIVE_SKIPPED: no -ArchiveFiles provided."
    exit 0
}

$archiveResults = New-Object System.Collections.Generic.List[object]
foreach ($path in $ArchiveFiles) {
    $rel = $path.TrimStart('\', '/')
    $result = Archive-ByTail -TargetRoot $targetPath -RelativePath $rel -ArchiveDir $ArchiveDir -KeepTailLines $KeepTailLines -DryRun:$DryRun
    $archiveResults.Add($result) | Out-Null
}

$archiveResults | Format-Table -AutoSize
Write-Host "DONE: auto archive finished."
