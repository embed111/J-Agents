param(
    [string]$PromptDir = "docs/workflow/prompts",
    [int]$Keep = 7
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PromptDir)) {
    Write-Host "Prompt dir not found: $PromptDir"
    exit 0
}

$files = Get-ChildItem -Path $PromptDir -File |
    Where-Object { $_.Name -like "执行提示词-*.md" } |
    Sort-Object LastWriteTime -Descending

if ($files.Count -le $Keep) {
    Write-Host "No trim needed. files=$($files.Count), keep=$Keep"
    exit 0
}

$toRemove = $files | Select-Object -Skip $Keep
foreach ($f in $toRemove) {
    Remove-Item -Force $f.FullName
    Write-Host "Removed: $($f.Name)"
}

Write-Host "Trim done. kept=$Keep removed=$($toRemove.Count)"
