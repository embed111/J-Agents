param(
    [string]$SourcePromptDir = "docs/workflow/prompts",
    [string]$TargetPromptDir = "../workflow/docs/workflow/prompts"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SourcePromptDir)) {
    Write-Host "Source prompt dir not found: $SourcePromptDir"
    exit 1
}

if (-not (Test-Path $TargetPromptDir)) {
    New-Item -ItemType Directory -Force -Path $TargetPromptDir | Out-Null
}

$sourceFiles = Get-ChildItem -Path $SourcePromptDir -File |
    Where-Object { $_.Name -like "执行提示词-*.md" } |
    Sort-Object Name

$targetFiles = Get-ChildItem -Path $TargetPromptDir -File |
    Where-Object { $_.Name -like "执行提示词-*.md" } |
    Sort-Object Name

$sourceNames = $sourceFiles | Select-Object -ExpandProperty Name

# Remove files that exist only in target.
$extras = $targetFiles | Where-Object { $sourceNames -notcontains $_.Name }
foreach ($file in $extras) {
    Remove-Item -Force $file.FullName
    Write-Host "Removed extra: $($file.Name)"
}

# Copy source files to target.
foreach ($file in $sourceFiles) {
    $dst = Join-Path $TargetPromptDir $file.Name
    Copy-Item -Force $file.FullName $dst
    Write-Host "Synced: $($file.Name)"
}

Write-Host "Done. source=$($sourceFiles.Count) target=$((Get-ChildItem -Path $TargetPromptDir -File | Where-Object { $_.Name -like '执行提示词-*.md' }).Count)"
