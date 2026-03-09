param(
    [int]$KeepSnapshotBlocks = 30,
    [int]$KeepChangeLogBlocks = 20,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-HeadingSections {
    param(
        [string[]]$Lines,
        [string]$HeadingRegex
    )
    $indexes = New-Object System.Collections.Generic.List[int]
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $HeadingRegex) {
            $indexes.Add($i)
        }
    }
    if ($indexes.Count -eq 0) {
        return $null
    }
    $prefix = @()
    if ($indexes[0] -gt 0) {
        $prefix = $Lines[0..($indexes[0] - 1)]
    }
    $sections = New-Object System.Collections.Generic.List[object]
    for ($j = 0; $j -lt $indexes.Count; $j++) {
        $start = $indexes[$j]
        $end = if ($j -lt $indexes.Count - 1) { $indexes[$j + 1] - 1 } else { $Lines.Count - 1 }
        $sections.Add(@($Lines[$start..$end]))
    }
    return @{
        Prefix = $prefix
        Sections = $sections
    }
}

function Extract-DateFromHeading {
    param([string]$Heading)
    if ($Heading -match "(\d{4}-\d{2}-\d{2})") {
        return $Matches[1]
    }
    return ""
}

function Remove-ArchiveRefBlock {
    param([string[]]$Lines)
    $start = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^## 历史归档引用") {
            $start = $i
            break
        }
    }
    if ($start -lt 0) {
        return $Lines
    }
    $end = $Lines.Count - 1
    for ($j = $start + 1; $j -lt $Lines.Count; $j++) {
        if ($Lines[$j] -match "^## ") {
            $end = $j - 1
            break
        }
    }
    $before = if ($start -gt 0) { $Lines[0..($start - 1)] } else { @() }
    $after = if ($end + 1 -lt $Lines.Count) { $Lines[($end + 1)..($Lines.Count - 1)] } else { @() }
    return @($before + $after)
}

function Write-IndexLine {
    param(
        [string]$IndexPath,
        [string]$Line
    )
    if (-not (Test-Path $IndexPath)) {
        $header = @(
            "# 历史归档索引",
            "",
            "- 说明: 仅归档历史块，保留顶层精简快照，不删除事实。",
            ""
        )
        Set-Content -Path $IndexPath -Value $header -Encoding UTF8
    }
    Add-Content -Path $IndexPath -Value $Line -Encoding UTF8
}

function Archive-FileByBlocks {
    param(
        [string]$FilePath,
        [string]$HeadingRegex,
        [int]$KeepBlocks,
        [string]$ArchiveDir,
        [string]$ArchivePrefix,
        [string]$IndexPath,
        [string]$SourceLabel
    )
    $lines = Get-Content -Path $FilePath
    $lines = Remove-ArchiveRefBlock -Lines $lines
    $parts = Get-HeadingSections -Lines $lines -HeadingRegex $HeadingRegex
    if ($null -eq $parts) {
        Write-Host "Skip ${SourceLabel}: heading not found"
        return @{
            changed = $false
            moved = 0
            total = 0
            archive = ""
        }
    }
    $sections = $parts.Sections
    if ($sections.Count -le $KeepBlocks) {
        Write-Host "Skip ${SourceLabel}: total blocks=$($sections.Count), keep=$KeepBlocks"
        return @{
            changed = $false
            moved = 0
            total = $sections.Count
            archive = ""
        }
    }
    $cut = $sections.Count - $KeepBlocks
    $movedSections = @($sections[0..($cut - 1)])
    $keptSections = @($sections[$cut..($sections.Count - 1)])

    $firstHeading = [string]$movedSections[0][0]
    $lastHeading = [string]$movedSections[$movedSections.Count - 1][0]
    $startDate = Extract-DateFromHeading -Heading $firstHeading
    $endDate = Extract-DateFromHeading -Heading $lastHeading
    if (-not $startDate) { $startDate = (Get-Date).ToString("yyyy-MM-dd") }
    if (-not $endDate) { $endDate = (Get-Date).ToString("yyyy-MM-dd") }

    if (-not (Test-Path $ArchiveDir)) {
        New-Item -ItemType Directory -Path $ArchiveDir -Force | Out-Null
    }
    $archiveName = "$ArchivePrefix-$startDate-to-$endDate.md"
    $archivePath = Join-Path $ArchiveDir $archiveName
    $repoPrefix = (Get-RepoRoot).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
    $archiveRel = $archivePath -replace [regex]::Escape($repoPrefix), ""
    $indexRel = $IndexPath -replace [regex]::Escape($repoPrefix), ""

    $archiveBody = New-Object System.Collections.Generic.List[string]
    $archiveBody.Add("# 历史归档")
    $archiveBody.Add("")
    $archiveBody.Add("- 归档时间: $((Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))")
    $archiveBody.Add("- 来源文件: $SourceLabel")
    $archiveBody.Add("- 覆盖区间: $startDate ~ $endDate")
    $archiveBody.Add("- 归档块数: $($movedSections.Count)")
    $archiveBody.Add("")
    foreach ($sec in $movedSections) {
        foreach ($line in $sec) {
            $archiveBody.Add([string]$line)
        }
    }

    $newTop = New-Object System.Collections.Generic.List[string]
    foreach ($line in $parts.Prefix) {
        $newTop.Add([string]$line)
    }
    if ($newTop.Count -gt 0 -and $newTop[$newTop.Count - 1] -ne "") {
        $newTop.Add("")
    }
    $newTop.Add("## 历史归档引用")
    $newTop.Add(("1. 已归档 {0} 个历史块到 `{1}`。" -f $movedSections.Count, $archiveRel))
    $newTop.Add(("2. 历史索引见 `{0}`。" -f $indexRel))
    $newTop.Add("")
    foreach ($sec in $keptSections) {
        foreach ($line in $sec) {
            $newTop.Add([string]$line)
        }
    }

    $indexLine = "1. $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) | $SourceLabel | $startDate ~ $endDate | moved=$($movedSections.Count) | file=$archiveRel"

    if ($DryRun) {
        Write-Host "DRY-RUN ${SourceLabel}: total=$($sections.Count) moved=$($movedSections.Count) keep=$KeepBlocks archive=$archiveRel"
        return @{
            changed = $true
            moved = $movedSections.Count
            total = $sections.Count
            archive = $archiveRel
        }
    }

    Set-Content -Path $archivePath -Value $archiveBody -Encoding UTF8
    Set-Content -Path $FilePath -Value $newTop -Encoding UTF8
    Write-IndexLine -IndexPath $IndexPath -Line $indexLine
    Write-Host "ARCHIVED ${SourceLabel}: total=$($sections.Count) moved=$($movedSections.Count) keep=$KeepBlocks archive=$archiveRel"
    return @{
        changed = $true
        moved = $movedSections.Count
        total = $sections.Count
        archive = $archiveRel
    }
}

$repoRoot = Get-RepoRoot
$sessionPath = Join-Path $repoRoot "workspace_state/core/session-snapshot.md"
$changePath = Join-Path $repoRoot "user_profile/logs/thinking-patterns-change-log.md"

if (-not (Test-Path $sessionPath)) {
    throw "Missing file: $sessionPath"
}
if (-not (Test-Path $changePath)) {
    throw "Missing file: $changePath"
}

$backupStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $repoRoot ".tmp/state-backups/$backupStamp"
if (-not $DryRun) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Copy-Item -Path $sessionPath -Destination (Join-Path $backupDir "session-snapshot.md.bak") -Force
    Copy-Item -Path $changePath -Destination (Join-Path $backupDir "thinking-patterns-change-log.md.bak") -Force
}

$sessionResult = Archive-FileByBlocks `
    -FilePath $sessionPath `
    -HeadingRegex "^## 本轮更新" `
    -KeepBlocks $KeepSnapshotBlocks `
    -ArchiveDir (Join-Path $repoRoot "workspace_state/logs/session-history") `
    -ArchivePrefix "session-history" `
    -IndexPath (Join-Path $repoRoot "workspace_state/logs/session-history-index.md") `
    -SourceLabel "workspace_state/core/session-snapshot.md"

$changeResult = Archive-FileByBlocks `
    -FilePath $changePath `
    -HeadingRegex "^## \d{4}-\d{2}-\d{2}" `
    -KeepBlocks $KeepChangeLogBlocks `
    -ArchiveDir (Join-Path $repoRoot "user_profile/logs/change-log-history") `
    -ArchivePrefix "thinking-patterns-change-log-history" `
    -IndexPath (Join-Path $repoRoot "user_profile/logs/change-log-history-index.md") `
    -SourceLabel "user_profile/logs/thinking-patterns-change-log.md"

Write-Host "DONE dry_run=$($DryRun.IsPresent) snapshot_changed=$($sessionResult.changed) changelog_changed=$($changeResult.changed)"

